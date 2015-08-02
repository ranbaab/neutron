# Copyright (c) 2015 Red Hat Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron.extensions import qos
from neutron import manager
from neutron.objects.qos import policy as policy_object
from neutron.plugins.common import constants as plugin_constants

NETWORK = 'network'
PORT = 'port'


# TODO(QoS): Add interface to define how this should look like
class QosResourceExtensionHandler(object):

    @property
    def plugin_loaded(self):
        if not hasattr(self, '_plugin_loaded'):
            service_plugins = manager.NeutronManager.get_service_plugins()
            self._plugin_loaded = plugin_constants.QOS in service_plugins
        return self._plugin_loaded

    def _get_policy_obj(self, context, policy_id):
        return policy_object.QosPolicy.get_by_id(context, policy_id)

    def _update_port_policy(self, context, port, port_changes):
        old_policy = policy_object.QosPolicy.get_port_policy(
            context, port['id'])
        if old_policy:
            #TODO(QoS): this means two transactions. One for detaching
            #           one for re-attaching, we may want to update
            #           within a single transaction instead, or put
            #           a whole transaction on top, or handle the switch
            #           at db api level automatically within transaction.
            old_policy.detach_port(port['id'])

        qos_policy_id = port_changes.get(qos.QOS_POLICY_ID)
        if qos_policy_id is not None:
            policy = self._get_policy_obj(context, qos_policy_id)
            #TODO(QoS): If the policy doesn't exist (or if it is not shared and
            #           the tenant id doesn't match the context's), this will
            #           raise an exception (policy is None).
            policy.attach_port(port['id'])
            port[qos.QOS_POLICY_ID] = qos_policy_id

    def _update_network_policy(self, context, network, network_changes):
        old_policy = policy_object.QosPolicy.get_network_policy(
            context, network['id'])
        if old_policy:
            old_policy.detach_network(network['id'])

        qos_policy_id = network_changes.get(qos.QOS_POLICY_ID)
        if qos_policy_id:
            policy = self._get_policy_obj(context, qos_policy_id)
            #TODO(QoS): If the policy doesn't exist (or if it is not shared and
            #           the tenant id doesn't match the context's), this will
            #           raise an exception (policy is None).
            policy.attach_network(network['id'])
            network[qos.QOS_POLICY_ID] = qos_policy_id

    def _exec(self, method_name, context, kwargs):
        return getattr(self, method_name)(context=context, **kwargs)

    def process_resource(self, context, resource_type, requested_resource,
                         actual_resource):
        if qos.QOS_POLICY_ID in requested_resource and self.plugin_loaded:
            self._exec('_update_%s_policy' % resource_type, context,
                       {resource_type: actual_resource,
                        "%s_changes" % resource_type: requested_resource})

    def extract_resource_fields(self, resource_type, resource):
        if not self.plugin_loaded:
            return {}

        binding = resource['qos_policy_binding']
        return {qos.QOS_POLICY_ID: binding['policy_id'] if binding else None}
