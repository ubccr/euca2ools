# Copyright 2009-2013 Eucalyptus Systems, Inc.
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

from euca2ools.commands.ec2 import EC2Request
from requestbuilder import Arg, Filter


class DescribeBundleTasks(EC2Request):
    DESCRIPTION = 'Describe current instance-bundling tasks'
    ARGS = [Arg('BundleId', metavar='BUNDLE', nargs='*',
                help='limit results to specific bundle tasks')]
    FILTERS = [Filter('bundle-id', help='bundle task ID'),
               Filter('error-code',
                      help='if the task failed, the error code returned'),
               Filter('error-message',
                      help='if the task failed, the error message returned'),
               Filter('instance-id', help='ID of the bundled instance'),
               Filter('progress', help='level of task completion, in percent'),
               Filter('s3-bucket',
                      help='bucket where the image will be stored'),
               Filter('s3-prefix', help='beginning of the bundle name'),
               Filter('start-time', help='task start time'),
               Filter('state', help='task state'),
               Filter('update-time', help='most recent task update time')]
    LIST_TAGS = ['bundleInstanceTasksSet']

    def print_result_native(self, result):
        for task in result.get('bundleInstanceTasksSet', []):
            self.print_bundle_task(task)
