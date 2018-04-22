#!/usr/bin/env python

from setuptools import setup

setup(
    name='dyndns53',
    license='MIT',
    author='Konstantin Malanchev',
    author_email='hombit@gmail.com',
    description='Just another dyndns client for AWS Route 53',
    scripts=['./dyndns53.py'],
    install_requires=['boto3'],
)
