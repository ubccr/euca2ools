# Copyright 2012-2014 Eucalyptus Systems, Inc.
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
from requestbuilder import Arg, MutuallyExclusiveArgList
from requestbuilder.exceptions import ArgumentError
import socket
import sys


class ModifySecurityGroupRequest(EC2Request):
    """
    The basis for security group-editing commands
    """

    ARGS = [Arg('group', metavar='GROUP', route_to=None,
                help='name or ID of the security group to modify (required)'),
            Arg('--egress', action='store_true', route_to=None,
                help='''[VPC only] manage an egress rule, which controls
                traffic leaving the group'''),
            Arg('-P', '--protocol', dest='IpPermissions.1.IpProtocol',
                choices=['tcp', 'udp', 'icmp', '6', '17', '1'], default='tcp',
                help='protocol to affect (default: tcp)'),
            Arg('-p', '--port-range', dest='port_range', metavar='RANGE',
                route_to=None, help='''range of ports (specified as "from-to")
                or a single port number (required for tcp and udp)'''),
            # ^ required for tcp and udp
            Arg('-t', '--icmp-type-code', dest='icmp_type_code',
                metavar='TYPE:CODE', route_to=None,
                help='''ICMP type and code (specified as "type:code") (required
                for icmp)'''),
            # ^ required for icmp
            MutuallyExclusiveArgList(
                Arg('-s', '--cidr', metavar='CIDR',
                    dest='IpPermissions.1.IpRanges.1.CidrIp',
                    help='''IP range (default: 0.0.0.0/0)'''),
                # ^ default is added by main()
                Arg('-o', dest='target_group', metavar='GROUP', route_to=None,
                    help='''[Non-VPC only] name of a security group with which
                    to affect network communication''')),
            Arg('-u', metavar='ACCOUNT',
                dest='IpPermissions.1.Groups.1.UserId',
                help='''ID of the account that owns the security group
                specified with -o''')]

    # noinspection PyExceptionInherit
    def configure(self):
        EC2Request.configure(self)

        if (self.args['group'].startswith('sg-') and
                len(self.args['group']) == 11):
            # The check could probably be a little better, but meh.  Fix if
            # needed.
            self.params['GroupId'] = self.args['group']
        else:
            if self.args['egress']:
                raise ArgumentError('egress rules must use group IDs, not '
                                    'names')
            self.params['GroupName'] = self.args['group']

        target_group = self.args.get('target_group')
        if (target_group is not None and target_group.startswith('sg-') and
                len(target_group) == 11):
            # Same note as above
            self.params['IpPermissions.1.Groups.1.GroupId'] = target_group
        else:
            if self.args['egress']:
                raise ArgumentError('argument -o: egress rules must use group '
                                    'IDs, not names')
            self.params['IpPermissions.1.Groups.1.GroupName'] = target_group

        protocol = self.args.get('IpPermissions.1.IpProtocol')
        if protocol in ['icmp', '1']:
            if self.args.get('port_range'):
                raise ArgumentError('argument -p/--port-range: not compatible '
                                    'with protocol ' + protocol)
            if not self.args.get('icmp_type_code'):
                self.args['icmp_type_code'] = '-1:-1'
            types = self.args['icmp_type_code'].split(':')
            if len(types) == 2:
                try:
                    from_port = int(types[0])
                    to_port = int(types[1])
                except ValueError:
                    raise ArgumentError('argument -t/--icmp-type-code: value '
                                        'must have format "1:2"')
            else:
                raise ArgumentError('argument -t/--icmp-type-code: value must '
                                    'have format "1:2"')
            if from_port < -1 or to_port < -1:
                raise ArgumentError('argument -t/--icmp-type-code: type, code '
                                    'must be at least -1')

        elif protocol in ['tcp', 'udp', '6', '17']:
            if self.args.get('icmp_type_code'):
                raise ArgumentError('argument -t/--icmp-type-code: not '
                                    'compatible with protocol ' + protocol)
            if not self.args.get('port_range'):
                raise ArgumentError('argument -p/--port-range is required for '
                                    'protocol ' + protocol)
            if ':' in self.args['port_range']:
                # Be extra helpful in the event of this common typo
                raise ArgumentError('argument -p/--port-range: multi-port '
                                    'range must be separated by "-", not ":"')
            from_port, to_port = _get_port_range(self.args['port_range'],
                                                 protocol)
            if from_port < -1 or to_port < -1:
                raise ArgumentError('argument -p/--port-range: port number(s) '
                                    'must be at least -1')
            if from_port == -1:
                from_port = 1
            if to_port == -1:
                to_port = 65535
        else:
            # Shouldn't get here since argparse should only allow the values we
            # handle
            raise ValueError('unrecognized protocol: "{0}"'.format(protocol))

        self.params['IpPermissions.1.FromPort'] = from_port
        self.params['IpPermissions.1.ToPort'] = to_port

        if (not self.args.get('IpPermissions.1.IpRanges.1.GroupName') and
                not self.args.get('IpPermissions.1.IpRanges.1.CidrIp')):
            # Default rule target is the entire Internet
            self.params['IpPermissions.1.IpRanges.1.CidrIp'] = '0.0.0.0/0'
        if (self.params.get('IpPermissions.1.Groups.1.GroupName') and
                not self.args.get('IpPermissions.1.Groups.1.UserId')):
            raise ArgumentError('argument -u is required when -o names a '
                                'security group by name')

    def print_result(self, _):
        print self.tabify(['GROUP', self.args.get('group')])
        perm_str = ['PERMISSION', self.args.get('group'), 'ALLOWS',
                    self.params.get('IpPermissions.1.IpProtocol'),
                    self.params.get('IpPermissions.1.FromPort'),
                    self.params.get('IpPermissions.1.ToPort')]
        if self.params.get('IpPermissions.1.Groups.1.UserId'):
            perm_str.append('USER')
            perm_str.append(self.params.get('IpPermissions.1.Groups.1.UserId'))
        if self.params.get('IpPermissions.1.Groups.1.GroupId'):
            perm_str.append('GRPID')
            perm_str.append(self.params.get(
                'IpPermissions.1.Groups.1.GroupId'))
        elif self.params.get('IpPermissions.1.Groups.1.GroupName'):
            perm_str.append('GRPNAME')
            perm_str.append(self.params.get(
                'IpPermissions.1.Groups.1.GroupName'))
        if self.params.get('IpPermissions.1.IpRanges.1.CidrIp'):
            perm_str.extend(['FROM', 'CIDR'])
            perm_str.append(self.params.get(
                'IpPermissions.1.IpRanges.1.CidrIp'))
        print self.tabify(perm_str)

    def process_cli_args(self):
        # We need to parse out -t and -p *before* argparse can see it because
        # of Python bug 9334, which prevents argparse from recognizing '-1:-1'
        # as an option value and not a (nonexistent) option name.
        saved_sys_argv = list(sys.argv)

        def parse_neg_one_value(opt_name):
            if opt_name in sys.argv:
                index = sys.argv.index(opt_name)
                if (index < len(sys.argv) - 1 and
                        sys.argv[index + 1].startswith('-1')):
                    opt_val = sys.argv[index + 1]
                    del sys.argv[index:index + 2]
                    return opt_val

        icmp_type_code = (parse_neg_one_value('-t') or
                          parse_neg_one_value('--icmp-type-code'))
        port_range = (parse_neg_one_value('-p') or
                      parse_neg_one_value('--port-range'))
        EC2Request.process_cli_args(self)
        if icmp_type_code:
            self.args['icmp_type_code'] = icmp_type_code
        if port_range:
            self.args['port_range'] = port_range
        sys.argv = saved_sys_argv


def _get_port_range(port_range, protocol):
    # Try for an integer
    try:
        return (int(port_range), int(port_range))
    except ValueError:
        pass
    # Try for an integer range
    if port_range.count('-') == 1:
        ports = port_range.split('-')
        try:
            return (int(ports[0]), int(ports[1]))
        except ValueError:
            pass
    # Try for a service name
    try:
        port = socket.getservbyname(port_range, protocol)
        return (port, port)
    except socket.error:
        pass
    # That's all, folks!
    raise ArgumentError("argument -p/--port-range: '{0}' is neither a port "
                        "number, range of port numbers, nor a recognized "
                        "service name".format(port_range))
