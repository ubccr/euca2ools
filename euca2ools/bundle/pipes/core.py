# Copyright 2013 Eucalyptus Systems, Inc.
#
# Redistribution and use of this software in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import hashlib
import multiprocessing
import os
import shutil
import subprocess
import sys
import tarfile

import euca2ools.bundle.util
from euca2ools.bundle.util import spawn_process, find_and_close_open_files

show_debug = False


def _create_tarball_from_stream(infile, outfile, tarinfo, debug=False):
    euca2ools.bundle.util.close_all_fds(except_fds=(infile, outfile))
    tarball = tarfile.open(mode='w|', fileobj=outfile,
                           bufsize=euca2ools.bundle.pipes._BUFSIZE)
    try:
        tarball.addfile(tarinfo, fileobj=infile)
    except IOError:
        # HACK
        if not debug:
            return
        raise
    finally:
        infile.close()
        tarball.close()
        outfile.close()


def create_bundle_pipeline(infile, outfile, enc_key, enc_iv, tarinfo,
                           debug=False):
    pids = []

    # infile -> tar
    tar_out_r, tar_out_w = euca2ools.bundle.util.open_pipe_fileobjs()
    tar_p = multiprocessing.Process(target=_create_tarball_from_stream,
                                    args=(infile, tar_out_w, tarinfo),
                                    kwargs={'debug': debug})
    tar_p.start()
    pids.append(tar_p.pid)
    infile.close()
    tar_out_w.close()

    # tar -> sha1sum
    digest_out_r, digest_out_w = euca2ools.bundle.util.open_pipe_fileobjs()
    digest_result_r, digest_result_w = multiprocessing.Pipe(duplex=False)
    digest_p = multiprocessing.Process(
        target=_calc_sha1_for_pipe,
        args=(tar_out_r, digest_out_w, digest_result_w))
    digest_p.start()
    pids.append(digest_p.pid)
    digest_out_w.close()
    digest_result_w.close()

    # sha1sum -> gzip
    try:
        gzip = subprocess.Popen(['pigz', '-c'], stdin=digest_out_r,
                                stdout=subprocess.PIPE, close_fds=True,
                                bufsize=-1)
    except OSError:
        gzip = subprocess.Popen(['gzip', '-c'], stdin=digest_out_r,
                                stdout=subprocess.PIPE, close_fds=True,
                                bufsize=-1)
    digest_out_r.close()
    pids.append(gzip.pid)

    # gzip -> openssl
    openssl = subprocess.Popen(['openssl', 'enc', '-e', '-aes-128-cbc',
                                '-K', enc_key, '-iv', enc_iv],
                               stdin=gzip.stdout, stdout=outfile,
                               close_fds=True, bufsize=-1)
    gzip.stdout.close()
    pids.append(openssl.pid)

    # Make sure something calls wait() on every child process
    for pid in pids:
        euca2ools.bundle.util.waitpid_in_thread(pid)

    # Return the connection the caller can use to obtain the final digest
    return digest_result_r


def create_unbundle_pipeline(outfile, enc_key, enc_iv, progressbar, writer_func, debug=False, **writerkwargs):
    """
    Creates a pipeline to perform the unbundle operation on the input provided by 'writer_func(writerkwargs)'.
    The resulting unbundled image will be written to 'outfile'.

    :param outfile: file  obj to write unbundled image to
    :param enc_key: the encryption key used to bundle the image
    :param enc_iv: the encyrption initialization vector used to bundle the image
    :param writer_func: the function used to feed the pipe the bundled input to be unbundled
    :param progressbar: the progressbar obj to be updated during the unbundle pipe's work flow
    :param writerkwargs: the keyword arguements used when calling writer_func. ie: writer_func(writerkwargs)
    :returns multiprocessing.Queue: Queue contains the checksum (sha1) for the unbundled image
    """
    pids = []
    print_debug('Starting test_unbundle_pipe_line...')

    print_debug( "Main pid. My pid: " + str(os.getpid())+", my parent pid:" + str(os.getppid()))
    #Create the sub processes
    # infile -> openssl
    openssl = _get_ssl_subprocess(enc_key, enc_iv, decrypt=True)
    pids.append(openssl.pid)

    # openssl -> gzip
    gzip = _get_gzip_subprocess(openssl.stdout, decompress=True)
    pids.append(gzip.pid)

    #Create pipe file objs to handle i/o...
    sha1_io_r, sha1_io_w = euca2ools.bundle.util.open_pipe_fileobjs()
    sha1_checksum_r, sha1_checksum_w = euca2ools.bundle.util.open_pipe_fileobjs()

    # gzip -> sha1sum
    sha1 = spawn_process(_calc_sha1_for_pipe, infile=gzip.stdout, outfile=sha1_io_w,
                        digest_out_pipe_w=sha1_checksum_w, debug=debug)
    pids.append(sha1.pid)

    # sha1sum -> tar
    progress_r, progress_w = euca2ools.bundle.util.open_pipe_fileobjs()
    tar = spawn_process(_do_tar_extract, infile=sha1_io_r, outfile=progress_w, debug=debug)
    pids.append(tar.pid)

    #start the writer method to feed the pipeline something to unbundle
    writerkwargs['outfile'] = openssl.stdin
    start_writer = spawn_process(writer_func, **writerkwargs)
    pids.append(start_writer.pid)

    openssl.stdin.close()
    progress_w.close()

    # tar -> final output and update progressbar
    _copy_with_progressbar(infile=progress_r, outfile=outfile, progressbar=progressbar)
    sha1_checksum_w.close()
    sha1_checksum = sha1_checksum_r.read()
    print_debug('done!!!')

    for t in [sha1, tar, start_writer]:
        t.join()

    # Return the queue the caller can use to obtain the final digest
    return  sha1_checksum


def create_unbundle_by_manifest_pipeline(outfile, manifest, source_dir, progressbar=None):
    """
    Creates a pipeline to perform the unbundle operation on parts specified in 'manifest'. Parts located in
    the local 'source_dir' are processed through the unbundle pipe and the resulting unbundled image is written
    to 'outfile'.

    :param outfile: file obj to write unbundled image to
    :param manifest: euca2ools.manifest obj
    :param source_dir: local path to dir containing bundle parts.
    :param progressbar: the progressbar obj to be updated during the unbundle pipe's work flow
    :returns multiprocessing.Queue: Queue contains the checksum (sha1) for the unbundled image
    """
    enc_key = manifest.enc_key
    enc_iv = manifest.enc_iv
    return create_unbundle_pipeline(outfile,
                                    enc_key,
                                    enc_iv,
                                    progressbar,
                                    _concatenate_parts_to_file_for_pipe,
                                    image_parts=manifest.image_parts,
                                    source_dir=source_dir)


def create_unbundle_stream_pipeline(inputfile, outfile, enc_key, enc_iv, progressbar=None):
    """
    Creates a pipeline to perform the unbundle operation on bundled input read in from 'inputfile'. The resulting
    unbundled image is written to 'outfile'.

    :param outfile: file obj to write unbundled image to
    :param inputfile: file obj to read bundled image input from
    :param enc_key: the encryption key used to bundle the image
    :param enc_iv: the encyrption initialization vector used to bundle the image
    :param progressbar: the progressbar obj to be updated during the unbundle pipe's work flow
    :returns multiprocessing.Queue: Queue contains the checksum (sha1) for the unbundled image
    """
    return create_unbundle_pipeline(outfile,
                                    enc_key,
                                    enc_iv,
                                    progressbar,
                                    _write_file_to_pipe,
                                    inputfile=inputfile)



def _copy_with_progressbar(infile, outfile, progressbar=None):
    """
    Synchronously copy data from infile to outfile, updating a progress bar
    with the total number of bytes copied along the way if one was provided,
    and return the number of bytes copied.

    This method must be run on the main thread.

    :param infile: file obj to read input from
    :param outfile: file obj to write output to
    :param progressbar: progressbar object to update with i/o information
    """
    bytes_written = 0
    if progressbar:
        progressbar.start()
    try:
        while not infile.closed:
            chunk = infile.read(euca2ools.bundle.pipes._BUFSIZE)
            if chunk:
                bytes_written += len(chunk)
                outfile.write(chunk)
                outfile.flush()
                if progressbar:
                    progressbar.update(bytes_written)

            else:
                break
    finally:
        if progressbar:
            progressbar.finish()
        infile.close()
        outfile.close()


def _get_ssl_subprocess(enc_key, enc_iv, decrypt=True):
    """
    Creates openssl encrypt/decrypt subprocess to be used in (un)bundle_pipeline
    :param enc_key: the encryption key to be used
    :param enc_iv: the encyrption initialization vector to be used
    :param decrypt: boolean. If True will decrypt. If false will encrypt.
    :returns: openssl subprocess
    :rtype: subprocess.Popen
    """
    print_debug('get_ssl_decrypt_subprocess...')
    action = '-e'
    if decrypt:
        action = '-d'
    openssl = subprocess.Popen(['openssl', 'enc', action, '-aes-128-cbc',
                                '-K', enc_key, '-iv', enc_iv],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               close_fds=True, bufsize=-1)
    euca2ools.bundle.util.waitpid_in_thread(openssl.pid)
    return openssl


def _get_gzip_subprocess(infile, decompress=True):
    """
    Creates gzip subprocess to be used in (un)bundle_pipeline

    :param infile: The file obj containing gzip input
    :param decompress: boolean. If True will used gzip decompress. If False will use gzip compress.
    :returns: gzip subprocess
    :rtype: subprocess.Popen obj
    """
    print_debug('get_gzip_subprocess...')
    gzip_args = ['-c']
    if decompress:
        gzip_args = ['-c', '-d']
    try:
        args = ['pigz']
        gzip = subprocess.Popen(['pigz'] + gzip_args, stdin=infile,
                                stdout=subprocess.PIPE, close_fds=True,
                                bufsize=-1)
        #gzip._set_cloexec_flag(gzip.stdin)
    except OSError:
        gzip = subprocess.Popen(['gzip'] + gzip_args, stdin=infile,
                                stdout=subprocess.PIPE, close_fds=True,
                                bufsize=-1)
    euca2ools.bundle.util.waitpid_in_thread(gzip.pid)
    return gzip



def _calc_sha1_for_pipe(infile, outfile, digest_out_pipe_w, debug=False):
    """
    Read data from infile and write it to outfile, calculating a running SHA1
    digest along the way.  When infile hits end-of-file, send the digest in
    hex form to result_mpconn and exit.
    """
    print_debug("_calc_sha1_for_pipe...")
    print_debug( "My pid: " + str(os.getpid())+", my parent pid:" + str(os.getppid()))
    find_and_close_open_files([infile,outfile,digest_out_pipe_w])
    total = 0
    digest = hashlib.sha1()
    try:
        while True:
            chunk = infile.read(euca2ools.bundle.pipes._BUFSIZE)
            if chunk:
                total += len(chunk)
                #print_debug('calc total:', total)
                digest.update(chunk)
                outfile.write(chunk)
                outfile.flush()
            else:
                print_debug('Done with sha1. Input file ', infile.fileno(), ' closed? ', infile.closed)
                break
        print_debug("_calc_sha1_for_pipe digest returning: ", digest.hexdigest())
        digest_out_pipe_w.write(digest.hexdigest())
        digest_out_pipe_w.flush()
        digest_out_pipe_w.close()
        print_debug('Digest sent to pipe')
    except IOError:
        # HACK
        if not debug:
            return
        raise
    finally:
        infile.close()
        outfile.close()



def _do_tar_extract(infile, outfile, debug=False):
    """
    Perform tar extract on infile and write to outfile
    :param infile: file obj providing input for tar
    :param outfile: file obj destination for tar output
    """
    print_debug('do_tar_extract...')
    print_debug("My pid: " + str(os.getpid())+", my parent pid:" + str(os.getppid()))
    find_and_close_open_files([infile,outfile])
    #sys.stdin.close()
    tarball = tarfile.open(mode='r|', fileobj=infile)
    try:
        tarinfo = tarball.next()
        shutil.copyfileobj(tarball.extractfile(tarinfo), outfile)
    except IOError:
        # HACK
        if not debug:
            return
        raise
    finally:
        tarball.close()
        infile.close()
        outfile.close()
        #os._exit(os.EX_OK)


def _concatenate_parts_to_file_for_pipe(outfile, image_parts, source_dir, debug=False):
    """
    Concatenate a list of 'image_parts' files found in 'source_dir' into pipeline fed by 'outfile'
    Parts are checked against checksum contained in part obj against calculated checksums as they are read/written.
    :param outfile: file obj used to output concatenated parts to
    :param image_parts: list of euca2ools.manifest.part objs
    :param source_dir: local path to parts contained in image_parts
    """
    print_debug("My pid: " + str(os.getpid())+", my parent pid:" + str(os.getppid()))
    find_and_close_open_files([outfile])
    part_count = len(image_parts)
    try:
        for part in image_parts:
            print_debug("Concatenating Part:" + str(part.filename))
            sha1sum = hashlib.sha1()
            part_file_path = source_dir + "/" + part.filename
            with open(part_file_path) as part_file:
                data = part_file.read(euca2ools.bundle.pipes._BUFSIZE)
                while data:
                    sha1sum.update(data)
                    outfile.write(data)
                    outfile.flush()
                    data = part_file.read(euca2ools.bundle.pipes._BUFSIZE)
                part_digest = sha1sum.hexdigest()
                print_debug("PART NUMBER:" + str(image_parts.index(part)) + "/"+ str(part_count))
                print_debug('Part sha1sum:' + str(part_digest))
                print_debug('Expected sum:' + str(part.hexdigest))
                if part_digest != part.hexdigest:
                    raise ValueError('Input part file may be corrupt '
                                     '(expected digest: {0}, actual: {1})'.format(part.hexdigest, part_digest))
    except IOError:
        # HACK
        if not debug:
            return
        raise
    finally:
        if part_file:
            part_file.close()
        print_debug('Concatentate done')
        print_debug('Closing write end of pipe after writing')
        outfile.close()


def _write_file_to_pipe(inputfile, outfile, debug=False):
    """
    Intended for reading from file 'inputfile' and writing to pipe via 'outfile'.
    :param outfile: file obj used for writing inputfile to
    :param inputfile: file obj used for reading input from to feed pipe at 'outfile'
    """
    try:
        shutil.copyfileobj(inputfile, outfile)
        '''
        while not inputfile.closed:
            data = inputfile.read(euca2ools.bundle.pipes._BUFSIZE)
            if data:
                outfile.write(data)
                outfile.flush()
            else:
                break
        '''
    except IOError:
        # HACK
        if not debug:
            return
        raise
    finally:
        print_debug('Done, closing write end of pipe after writing')
        inputfile.close()
        outfile.close()


def print_debug(msg, *args):
    if show_debug:
        msg += " ".join(str(x) for x in args)
        print >> sys.stderr, msg


