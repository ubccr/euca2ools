# Copyright 2014 Eucalyptus Systems, Inc.
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

from requestbuilder import Arg, Filter, GenericTagFilter

from euca2ools.commands.ec2 import EC2Request


class DescribeCustomerGateways(EC2Request):
    DESCRIPTION = 'Show information about VPN customer gateways'
    ARGS = [Arg('CustomerGatewayId', metavar='CGATEWAY', nargs='*',
                help='limit results to specific customer gateways')]
    FILTERS = [Filter('bgp-asn', help='BGP AS number in use'),
               Filter('customer-gateway-id', help='customer gateway ID'),
               Filter('ip-address', help='''ID of the customer gateway's
                      cloud-facing interface'''),
               Filter('state', help='''customer gateway state (pending,
                      available, deleting, deleted)'''),
               Filter('tag-key',
                      help='key of a tag assigned to the customer gateway'),
               Filter('tag-value',
                      help='value of a tag assigned to the customer gateway'),
               GenericTagFilter('tag:KEY',
                                help='specific tag key/value combination'),
               Filter('type', help='the type of customer gateway (ipsec.1)')]

    LIST_TAGS = ['customerGatewaySet', 'tagSet']

    def print_result_native(self, result):
        for cgw in result.get('customerGatewaySet', []):
            self.print_customer_gateway(cgw)
