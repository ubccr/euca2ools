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

import json

class DescribeAddresses(EC2Request):
    DESCRIPTION = 'Show information about elastic IP addresses'
    ARGS = [Arg('address', metavar='ADDRESS', nargs='*', route_to=None,
                help='''limit results to specific elastic IP addresses or
                VPC allocation IDs''')]
    FILTERS = [Filter('allocation-id', help='[VPC only] allocation ID'),
               Filter('association-id', help='[VPC only] association ID'),
               Filter('domain', help='''whether the address is a standard
                      ("standard") or VPC ("vpc") address'''),
               Filter('instance-id',
                      help='instance the address is associated with'),
               Filter('network-interface-id', help='''[VPC only] network
                      interface the address is associated with'''),
               Filter('network-interface-owner-id', help='''[VPC only] ID of
                      the network interface's owner'''),
               Filter('private-ip-address', help='''[VPC only] private address
                      associated with the public address'''),
               Filter('public-ip', help='the elastic IP address')]
    LIST_TAGS = ['addressesSet']

    def preprocess(self):
        alloc_ids = set(addr for addr in self.args.get('address', [])
                        if addr.startswith('eipalloc-'))
        public_ips = set(self.args.get('address', [])) - alloc_ids
        if alloc_ids:
            self.params['AllocationId'] = list(sorted(alloc_ids))
        if public_ips:
            self.params['PublicIp'] = list(sorted(public_ips))

    def print_result(self, result):
        if self.args['json']:
            print json.dumps(result, sort_keys=True, indent=2)
            return
        for addr in result.get('addressesSet', []):
            print self.tabify(('ADDRESS', addr.get('publicIp'),
                               addr.get('instanceId'),
                               addr.get('domain', 'standard'),
                               addr.get('allocationId'),
                               addr.get('associationId'),
                               addr.get('networkInterfaceId'),
                               addr.get('privateIpAddress')))
