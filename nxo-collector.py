#!/usr/bin/env python
import atexit
import logging
import argparse
import getpass
import pprint
import re
import json

from pyVim import connect
from pyVmomi import vmodl
from pyVmomi import vim


def main():
    """
    Simple command-line program for listing the virtual machines on a system.
    """

    #args = cli.get_args()
    
    parser = argparse.ArgumentParser(
        description='Standard Arguments for talking to vCenter')

    # because -h is reserved for 'help' we use -s for service
    parser.add_argument('-s', '--host',
                        required=True,
                        action='store',
                        help='vSphere service to connect to')

    # because we want -p for password, we use -o for port
    parser.add_argument('-o', '--port',
                        type=int,
                        default=443,
                        action='store',
                        help='Port to connect on')

    parser.add_argument('-u', '--user',
                        required=True,
                        action='store',
                        help='User name to use when connecting to host')

    parser.add_argument('-f', '--file',
                        required=True,
                        action='store',
                        help='Where to store the file output')

    parser.add_argument('-p', '--password',
                        required=False,
                        action='store',
                        help='Password to use when connecting to host')

    parser.add_argument('-S', '--disable_ssl_verification',
                        required=False,
                        action='store_true',
                        help='Disable ssl host certificate verification')



    args = parser.parse_args()

    if not args.password:
        args.password = getpass.getpass(
            prompt='Enter password for host %s and user %s: ' %
                   (args.host, args.user))

    try:
        if args.disable_ssl_verification:
            service_instance = connect.SmartConnectNoSSL(host=args.host,
                                                         user=args.user,
                                                         pwd=args.password,
                                                         port=int(args.port))
        else:
            service_instance = connect.SmartConnect(host=args.host,
                                                    user=args.user,
                                                    pwd=args.password,
                                                    port=int(args.port))

        atexit.register(connect.Disconnect, service_instance)

        collector = service_instance.content.propertyCollector

        # TODO: parametrize?
        path_set = ['name', 'config.uuid', 'summary.config.memorySizeMB', 'config.hardware.numCPU', 'runtime.powerState', 'config.hardware.device']
        obj_type = vim.VirtualMachine
        container = service_instance.content.rootFolder
        include_mors = False
        view_ref = service_instance.content.viewManager.CreateContainerView(
                container=container,
                type=[obj_type],
                recursive=True
        )

        # Create object specification to define the starting point of
        # inventory navigation
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec()
        obj_spec.obj = view_ref
        obj_spec.skip = True

        # Create a traversal specification to identify the
        # path for collection
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec()
        traversal_spec.name = 'traverseEntities'
        traversal_spec.path = 'view'
        traversal_spec.skip = False
        traversal_spec.type = view_ref.__class__
        obj_spec.selectSet = [traversal_spec]

        # Identify the properties to the retrieved
        property_spec = vmodl.query.PropertyCollector.PropertySpec()
        property_spec.type = obj_type

        if not path_set:
            logging.warning(
                    '[%s] Retrieving all properties for objects, this might take a while...',
                    args.host
            )
            property_spec.all = True

        property_spec.pathSet = path_set

        # Add the object and property specification to the
        # property filter specification
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = [obj_spec]
        filter_spec.propSet = [property_spec]

        # Retrieve properties
        props = collector.RetrieveContents([filter_spec])

        data = []
        for obj in props:
            properties = {}
            for prop in obj.propSet:
                properties[prop.name] = prop.val

            if include_mors:
                properties['obj'] = obj.obj

            data.append(properties)

        pp = pprint.PrettyPrinter(indent=4)
        NAME=[]
        POWERSTATE=[]
        VCPU=[]
        VRAM=[]
        VDISKs=[]
        TotalCapacity=[]
        DiskExist=[]
        for j in range(len(data)):
            NAME.append(data[j]['name'])
            if data[j]['runtime.powerState']=='poweredOn':
                POWERSTATE.append('On')
            elif data[j]['runtime.powerState']=='poweredOff':
                POWERSTATE.append('Off')
            else:
                POWERSTATE.append('Suspended')
            VCPU.append(data[j]['config.hardware.numCPU'])
            VRAM.append(int(data[j]['summary.config.memorySizeMB'])*1024*1024)
            newIndex=0
            DiskCapacities=[]
            SumOfDiskCapacities=0
            
            for i in data[j]['config.hardware.device']:
                if isinstance(i, vim.vm.device.VirtualDisk):
                    newIndex +=1 #print(i.capacityInBytes)
                    DiskCapacities.append(i.capacityInBytes)
                    SumOfDiskCapacities += i.capacityInBytes
            if newIndex==0:
                VDISKs.append([0])
                DiskExist.append('No')
            else:
                VDISKs.append(DiskCapacities)
                DiskExist.append('Yes')
            TotalCapacity.append(SumOfDiskCapacities)
        print(DiskExist)
        VMs=[]
        for i in range(len(NAME)):
            vdiskslist=[]
            for j in range(len(VDISKs[i])):
                if DiskExist[i]== 'No':
                    vdiskslist.append({})  
                else:
                    vdiskslist.append({"capacity":VDISKs[i][j]})
            VMspecs={"name": NAME[i], "powerstate": POWERSTATE[i], "vcpu": VCPU[i], "ram":VRAM[i],"vdisks": vdiskslist}
            VMs.append(VMspecs)
        output={'version':1,'source':'vmware','vms':VMs}
        with open(args.file,'w') as outfile:
            json.dump(output, outfile)





    except vmodl.MethodFault as error:
        print("Caught vmodl fault : " + error.msg)
        return -1

# Start program
if __name__ == "__main__":
    main()