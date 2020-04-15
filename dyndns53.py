#!/usr/bin/env python

import logging
from copy import deepcopy

import boto3


GET_IP_URLS=(
    'https://api.ipify.org',
    'http://ipinfo.io/ip',
    'http://bot.whatismyipaddress.com',
    'http://icanhazip.com',
    'https://www.trackip.net/ip',
)


def _get_ip():
    import requests

    for url in GET_IP_URLS:
        try:
            return requests.get(url).text
        except requests.exceptions.RequestException as e:
            logging.info(str(e))
    raise RuntimeError('Cannot get IP')


def route53(hostname, force=False, ip=None):
    if ip is None:
        ip = _get_ip()

    roothostname = '.'.join( hostname.split('.')[-2:] )
    recordname = hostname + '.'

    client = boto3.client('route53')

    try:
        Id = client.list_hosted_zones_by_name(DNSName=roothostname, MaxItems='1')['HostedZones'][0]['Id']
    except KeyError as e:
        raise ValueError("Route53 hosted zone {} doesn't exist".format(roothostname)) from e

    current_record = client.list_resource_record_sets(
        HostedZoneId=Id,
        StartRecordName=recordname,
        StartRecordType='A',
        MaxItems='1'
    )['ResourceRecordSets'][0]

    if current_record['Name'] != recordname:
        if not force:
            msg = "Hostname {} isn't found at Route53, use force to create".format(hostname)
            logging.error(msg)
            raise ValueError(msg)
        current_ip = None
    else:
        current_ip = current_record['ResourceRecords'][0]['Value']

    if ip == current_ip:
        logging.info("Skipping update for {}, IP hasn't been changed".format(hostname))
        return

    response = client.change_resource_record_sets(
        HostedZoneId=Id,
        ChangeBatch={
            'Comment': 'Automatically update A record for host {}'.format(hostname),
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': recordname,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': ip}]
                    },
                }
            ]
        }
    )
    logging.info('{} address is updated to {}, response: {}'.format(hostname, ip, str(response)))


################################################################################


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', '-i', type=str,
                        help='Manually set IP, default is to set public IP of the host')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Verbose logging, default is ERROR, -v is WARNING, -vv is INFO')
    parser.add_argument('-f', '--force', action='store_true', help="Create record if it doesn't exist")
    parser.add_argument('hostname', type=str, metavar='HOST', nargs='+',
                        help='Hostname to update')
    args = parser.parse_args()

    logging_level = logging.INFO
    if args.verbose == 0:
        logging_level = logging.ERROR
    elif args.verbose == 1:
        logging_level= logging.WARNING
    logging.basicConfig(level=logging_level)

    for hostname in args.hostname:
        route53(hostname, force=args.force, ip=args.ip)
