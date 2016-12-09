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


class DescribeAvailabilityZones(EC2Request):
    DESCRIPTION = 'Display availability zones within the current region'
    ARGS = [Arg('ZoneName', metavar='ZONE', nargs='*',
                help='limit results to specific availability zones')]
    FILTERS = [Filter('message', help='''message giving information about the
                      availability zone'''),
               Filter('region-name',
                      help='region the availability zone is in'),
               Filter('state', help='state of the availability zone'),
               Filter('zone-name', help='name of the availability zone')]
    LIST_TAGS = ['availabilityZoneInfo', 'messageSet']

    def print_result_plain(self, result):
        for zone in result.get('availabilityZoneInfo', []):
            msgs = ', '.join(msg for msg in zone.get('messageSet', []))
            print self.tabify(('AVAILABILITYZONE', zone.get('zoneName'),
                               zone.get('zoneState'), msgs))
