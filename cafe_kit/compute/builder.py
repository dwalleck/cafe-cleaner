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
import functools
import multiprocessing
import random
import time
import traceback

from prettytable import PrettyTable

from cafe.configurator.managers import TestEnvManager
from cloudcafe.compute.composites import ComputeComposite
from cloudcafe.compute.common.exceptions import BuildErrorException


def entry_point():

    # Set up arguments
    argparser = argparse.ArgumentParser(prog='cafe-builder')

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

    argparser.add_argument(
        "num_servers",
        nargs=1,
        metavar="<num_servers>",
        help="Number of servers to build")

    argparser.add_argument(
        "--ramp-up",
        nargs=1,
        metavar="<ramp_up>",
        help="Amount of time in seconds over which server "
             "requests will be made")

    args = argparser.parse_args()
    config = str(args.config[0])
    product = str(args.product[0])
    num_servers = int(args.num_servers[0])
    ramp_up_time = 0
    if args.ramp_up:
        ramp_up_time = int(args.ramp_up[0])

    test_env_manager = TestEnvManager(product, config)
    test_env_manager.finalize()
    builder(num_servers, ramp_up_time)
    exit(0)


def create_server(ramp_up_time=0):
    local_random = random.Random()
    wait = local_random.randint(0, ramp_up_time)
    time.sleep(wait)

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
        response = compute.servers.behaviors.create_server_with_defaults()
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


def builder(num_servers, ramp_up_time):

    pool = multiprocessing.Pool(num_servers)
    create_func = functools.partial(
        create_server, ramp_up_time=ramp_up_time)
    start_time = time.time()
    tests = [pool.apply_async(create_func)
             for iteration in xrange(num_servers)]
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