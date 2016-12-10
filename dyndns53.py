#!/usr/bin/env python3


import boto3
from copy import deepcopy


GET_IP_URLS=(
    'https://api.ipify.org',
    'http://ipinfo.io/ip',
    'http://bot.whatismyipaddress.com',
    'http://icanhazip.com',
    'https://www.trackip.net/ip',
)


def _get_ip():
    from requests import get
    for url in GET_IP_URLS:
        try:
            return get(url).text
        except:
            pass
    raise(RuntimeError('Cannot get IP'))


def dyndns(hostname, ip=None):
    if ip is None:
        ip = _get_ip()

    roothostname = '.'.join( hostname.split('.')[-2:] )

    client = boto3.client('route53')
    Id = client.list_hosted_zones_by_name(DNSName=roothostname, MaxItems='1')['HostedZones'][0]['Id']
    current_record = client.list_resource_record_sets(
        HostedZoneId=Id,
        StartRecordName=hostname+'.',
        StartRecordType='A',
        MaxItems='1'
    )['ResourceRecordSets'][0]
    current_ip = current_record['ResourceRecords'][0]['Value']

    if ip != current_ip:
        new_record = deepcopy(current_record)
        new_record['ResourceRecords'][0]['Value'] = ip

        response = client.change_resource_record_sets(
            HostedZoneId=Id,
            ChangeBatch={
                'Comment': 'Automatically update A record for host {}'.format(hostname),
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': new_record,
                    }
                ]
            }
        )
        return response
    else:
        return "Skipping update, IP haven't been changed"


################################################################################


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', '-i', type=str,
                        help='Manually set IP, default is to set public IP of the host')
    parser.add_argument('hostname', type=str, metavar='HOST', nargs='+',
                        help='Hostname to update')
    args = parser.parse_args()

    for hostname in args.hostname:
        print(dyndns(hostname, ip=args.ip))