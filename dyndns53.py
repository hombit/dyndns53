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


def _root_host_name(hostname):
    return '.'.join(hostname.split('.')[-2:])


def route53(hostname, ip, force=False):
    zone_name = _root_host_name(hostname)
    recordname = hostname + '.'

    client = boto3.client('route53')

    try:
        Id = client.list_hosted_zones_by_name(DNSName=zone_name, MaxItems='1')['HostedZones'][0]['Id']
    except KeyError as e:
        raise ValueError("Route53 hosted zone {} doesn't exist".format(zone_name)) from e

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


def pdd(hostname, ip, force=False):
    from os import environ

    from requests import get, post

    base_url = 'https://pddimp.yandex.ru/api2/admin/dns/'

    try:
        token = environ['PDD_TOKEN']
    except KeyError:
        raise RuntimeError('PDD_TOKEN environment variable must be set')

    domain = _root_host_name(hostname)

    response = get(
        base_url + 'list',
        params={'domain': domain},
        headers={'PddToken': token}
    ).json()
    if response['success'] != 'ok':
        msg = 'Response has failed with error {}'.format(response['error'])
        logging.error(msg)
        raise RuntimeError(msg)

    params = {
        'domain': domain,
        'subdomain': hostname,
        'content': ip,
    }
    for record in response['records']:
        if record['type'] != 'A':
            continue
        if 'subdomain' not in record:
            continue
        record_hostname = '{}.{}'.format(record['subdomain'], domain)
        if record_hostname == hostname:
            current_ip = record['content']
            if ip == current_ip:
                logging.info("Skipping update for {}, IP hasn't been changed".format(hostname))
                return
            url = base_url + 'edit'
            params['record_id'] = record['record_id']
            break
    else:
        if not force:
            msg = "Hostname {} isn't found at Yandex PDD, use force to create".format(hostname)
            logging.error(msg)
            raise ValueError(msg)
        url = base_url + 'add'
        params['type'] = 'A'

    response = post(url, params=params, headers={'PddToken': token}).json()
    if response['success'] != 'ok':
        msg = 'Response has failed with error {}'.format(response['error'])
        logging.error(msg)
        raise RuntimeError(msg)
    logging.info('{} address is updated to {}, response: {}'.format(hostname, ip, str(response)))


PROVIDERS = {
    'amazon': route53,
    'yandex': pdd,
}


################################################################################


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', '-i', type=str,
                        help='Manually set IP, default is to set public IP of the host')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Verbose logging, default is ERROR, -v is WARNING, -vv is INFO')
    parser.add_argument('-f', '--force', action='store_true', help="Create record if it doesn't exist")
    parser.add_argument('-p', '--provider', type=str, default='amazon', help='DNS provider: amazon or yandex')
    parser.add_argument('hostname', type=str, metavar='HOST', nargs='+',
                        help='Hostname to update')
    args = parser.parse_args()

    logging_level = logging.INFO
    if args.verbose == 0:
        logging_level = logging.ERROR
    elif args.verbose == 1:
        logging_level= logging.WARNING
    logging.basicConfig(level=logging_level)

    try:
        provider = PROVIDERS[args.provider]
    except KeyError:
        msg = "DNS provider {} isn't supported, supported providers are {}".format(args.provider, ', '.join(PROVIDERS))
        logging.error(msg)
        raise ValueError(msg)

    ip = args.ip or _get_ip()

    for hostname in args.hostname:
        provider(hostname, ip, force=args.force)
