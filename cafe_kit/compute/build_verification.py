"""
Copyright 2014 Rackspace

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
import functools
import multiprocessing
import time
import traceback

from prettytable import PrettyTable

from cafe.configurator.managers import TestEnvManager
from cloudcafe.compute.composites import ComputeComposite


def entry_point():

    # Set up arguments
    argparser = argparse.ArgumentParser(prog='cafe-build-all')

    argparser.add_argument(
        "product",
        metavar="<product>",
        help="Product name")

    argparser.add_argument(
        "config",
        metavar="<config_file>",
        help="Product test config")

    argparser.add_argument(
        "--image-filter",
        metavar="<image_filter>",
        help="")

    argparser.add_argument(
        "--flavor-filter",
        metavar="<flavor_filter>",
        help="")

    argparser.add_argument(
        "--key",
        metavar="<key>",
        help="The name of a existing Compute keypair. "
             "A keypair is required for OnMetal instances.")

    args = argparser.parse_args()
    config = args.config
    product = args.product
    key = args.key

    test_env_manager = TestEnvManager(product, config)
    test_env_manager.finalize()
    compute = ComputeComposite()

    image_filter = args.image_filter
    resp = compute.images.client.list_images()
    images = resp.entity

    filtered_images = filter(lambda i: image_filter in i.name, images)

    flavor_filter = args.flavor_filter
    resp = compute.flavors.client.list_flavors_with_detail()
    flavors = resp.entity

    filtered_flavors = filter(lambda f: flavor_filter in f.name, flavors)
    pairs = list(generate_image_flavor_pairs(filtered_images, filtered_flavors))

    builder(pairs, key)
    exit(0)


def generate_image_flavor_pairs(images, flavors):
    for image in images:
        for flavor in flavors:
            yield image.id, flavor.id


def create_server(image_id, flavor_id, key=None):
    passed = True
    response = None
    message = None

    for i in range(5):
        try:
            compute = ComputeComposite()
            break
        except Exception as ex:
            print 'Error authenticating:'
            traceback.print_exc()
            print 'Retrying.'

    start_time = time.time()
    try:

        response = compute.servers.behaviors.create_server_with_defaults(
            image_ref=image_id, flavor_ref=flavor_id, key_name=key)
        compute.servers.behaviors.wait_for_server_creation(
            response.entity.id)

    except Exception as ex:
        traceback.print_exc()
        passed = False
    finish_time = time.time()

    server_id = None
    if response and response.entity:
        server_id = response.entity.id
        server = compute.servers.client.get_server(server_id).entity

        # If there is a fault for the server, add it to the result
        if server.fault:
            message = server.fault.message

        compute.servers.client.delete_server(server.id)

    return passed, server_id, finish_time - start_time, message


def builder(pairs, key):
    num_servers = len(pairs)
    pool = multiprocessing.Pool(8)
    create_funcs = [functools.partial(create_server, image_id, flavor_id, key)
                    for image_id, flavor_id in pairs]

    start_time = time.time()
    tests = [pool.apply_async(create_func)
             for create_func in create_funcs]
    results = [test.get() for test in tests]
    finish_time = time.time()
    run_time = finish_time - start_time

    passes = 0
    errored = 0
    total_time = 0

    results_table = PrettyTable(
        ["Server Id", "Successful?", "Build Time (s)", "Faults"])
    results_table.align["Server Id"] = "l"

    for passed, server_id, build_time, message in results:
        if passed:
            passes += 1
        else:
            errored += 1
        total_time += build_time
        results_table.add_row([server_id, passed, build_time, message])

    average_time = total_time / num_servers
    print results_table
    print "Servers built: " + str(num_servers)
    print "Passed: " + str(passes)
    print "Errored: " + str(errored)
    print "Average Build Time: " + str(average_time)
    print "Execution time: " + str(run_time)

if __name__ == '__main__':
    entry_point()