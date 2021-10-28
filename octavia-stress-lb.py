from __future__ import print_function
import sys
import os
import time
import collections
import yaml
import openstack
import multiprocessing
import time


def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())
yaml.add_representer(collections.OrderedDict, dict_representer)

if type(u'string') != str:
    def unicode_representer(dumper, data):
        return dumper.represent_str(str(data))
    yaml.add_representer(unicode, unicode_representer)

def config_from_env():
    config = {}
    for k in ('auth_url', 'project_name', 'username',
              'password', 'region_name'):
        v = os.environ.get('OS_%s' % (k.upper()))
        config[k] = v
    return config

def create_resources(conn, lb_id):
    listener_kwargs = {
        'protocol': 'HTTP',
        'protocol_port': 80,
        'loadbalancer_id': lb_id
    }
    print("{} Adding a listener".format(lb_id))
    listener = conn.load_balancer.create_listener(**listener_kwargs)
    wait_for_lb(conn, lb_id)

    pool_kwargs = {
        'listener_id': listener.id,
        'lb_algorithm': 'ROUND_ROBIN',
        'protocol': 'HTTP'
    }
    print("{} Adding a pool".format(lb_id))
    pool = conn.load_balancer.create_pool(**pool_kwargs)
    wait_for_lb(conn, lb_id)

    for i in range(1, 4):
        member_kwargs = {
            'address': '192.168.0.{}'.format(i),
            'protocol_port': 80,
        }
        print("{} Adding a member".format(lb_id))
        member = conn.load_balancer.create_member(pool.id, **member_kwargs)
        wait_for_lb(conn, lb_id)

def create_and_delete(conn, lb_id):
    subnet = conn.network.find_subnet('private_subnet')

    lb_kwargs = {
        'vip_subnet_id': subnet.id,
        'name': 'lb-{}'.format(lb_id)
    }
    lb = conn.load_balancer.create_load_balancer(**lb_kwargs)
    print("{} Creating {}".format(lb.id, lb_id))
    wait_for_lb(conn, lb.id)

    lb = conn.load_balancer.get_load_balancer(lb)
    if lb.provisioning_status == 'ACTIVE':
        create_resources(conn, lb.id)
    else:
        time.sleep(10)

    print("{} Deleting".format(lb.id))
    conn.load_balancer.delete_load_balancer(lb.id, cascade=True)
    wait_for_lb_deleted(conn, lb)

def wait_for_lb(conn, lb_id):
    #print("Waiting for %s (%s) to be active" % (lb.name, lb.id))
    sys.stdout.flush()
    while range(0, 120):
        lb = conn.load_balancer.get_load_balancer(lb_id)
        sys.stdout.flush()
        if lb.provisioning_status in ('ACTIVE', 'ERROR'):
            print("{} is in {} state".format(
                lb.id, lb.provisioning_status))
            break
        time.sleep(1)
    else:
        print(lb)
        raise Exception("")

def wait_for_lb_deleted(conn, lb):
    #print("Waiting for %s (%s) to be deleted" % (lb.name, lb.id))
    sys.stdout.flush()
    while range(0, 120):
        try:
            lb = conn.load_balancer.get_load_balancer(lb)
        except (openstack.exceptions.ResourceNotFound,
                openstack.exceptions.NotFoundException):
            print("{} is DELETED".format(lb.id))
            break
        sys.stdout.flush()
        if lb.provisioning_status == 'DELETED':
            print("{} is in {} state".format(
                lb.id, lb.provisioning_status))
            break
        if lb.provisioning_status == "ERROR":
            print("XXX {} is in the invalid ERROR state".format(lb.id))
            break
        time.sleep(1)
    else:
        print(lb)
        raise Exception("")

openstack.enable_logging()

def func(lb_id):
    #time.sleep((120 / 20) * (lb_id % 20))
    conn = openstack.connect(**config_from_env())
    create_and_delete(conn, lb_id)

nb_threads = 20

pool = multiprocessing.Pool(nb_threads)
pool.map(func, range(0, 3000))
