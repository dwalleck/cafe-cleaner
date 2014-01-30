"""
Copyright 2013 Rackspace

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import traceback

from cafe.configurator.managers import TestEnvManager

from cloudcafe.compute.config import ComputeEndpointConfig, \
    MarshallingConfig
from cloudcafe.compute.common.exception_handler import ExceptionHandler
from cloudcafe.compute.flavors_api.client import FlavorsClient
from cloudcafe.compute.servers_api.client import ServersClient
from cloudcafe.compute.images_api.client import ImagesClient
from cloudcafe.compute.extensions.keypairs_api.client import KeypairsClient
from cloudcafe.auth.config import UserAuthConfig, UserConfig
from cloudcafe.auth.provider import AuthProvider


def entry_point():

    # Set up arguments
    argparser = argparse.ArgumentParser(prog='cafe-cleaner')

    argparser.add_argument(
        "product",
        nargs=1,
        metavar="<product>",
        help="Product name")

    argparser.add_argument(
        "config",
        nargs=1,
        metavar="<config_file>",
        help="Product test config")

    args = argparser.parse_args()
    config = str(args.config[0])
    product = str(args.product[0])

    test_env_manager = TestEnvManager(product, config)
    test_env_manager.finalize()
    compute_cleanup()
    exit(0)


def compute_cleanup():
    # Load necessary configurations
    compute_endpoint = ComputeEndpointConfig()
    marshalling = MarshallingConfig()

    endpoint_config = UserAuthConfig()
    user_config = UserConfig()
    access_data = AuthProvider.get_access_data(
        endpoint_config, user_config)

    # If authentication fails, halt
    if access_data is None:
        raise Exception('Authentication failed.')

    compute_service = access_data.get_service(
        compute_endpoint.compute_endpoint_name)
    url = compute_service.get_endpoint(
        compute_endpoint.region).public_url
    # If a url override was provided, use that value instead
    if compute_endpoint.compute_endpoint_url:
        url = '{0}/{1}'.format(compute_endpoint.compute_endpoint_url,
                               user_config.tenant_id)

    client_args = {'url': url, 'auth_token': access_data.token.id_,
                   'serialize_format': marshalling.serializer,
                   'deserialize_format': marshalling.deserializer}

    flavors_client = FlavorsClient(**client_args)
    servers_client = ServersClient(**client_args)
    images_client = ImagesClient(**client_args)
    keypairs_client = KeypairsClient(**client_args)
    flavors_client.add_exception_handler(ExceptionHandler())

    keys = keypairs_client.list_keypairs().entity
    print 'Preparing to delete {count} keys...'.format(count=len(keys))
    for key in keys:
        try:
            keypairs_client.delete_keypair(key.name)
        except Exception:
            print 'Failed to delete key {id}: {exception}'.format(
                id=key.id, exception=traceback.format_exc())

    servers = servers_client.list_servers_with_detail().entity
    print 'Preparing to delete {count} servers...'.format(count=len(servers))
    for server in servers:
        try:
            servers_client.delete_server(server.id)
        except Exception:
            print 'Failed to delete server {id}: {exception}'.format(
                id=server.id, exception=traceback.format_exc())

    images = images_client.list_images(image_type='snapshot').entity
    print 'Preparing to delete {count} image snapshots...'.format(count=len(images))
    for image in images:
        try:
            images_client.delete_image(image.id)
        except Exception:
            print 'Failed to delete image {id}: {exception}'.format(
                id=image.id, exception=traceback.format_exc())


if __name__ == '__main__':
    entry_point()
