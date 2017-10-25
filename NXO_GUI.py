#!/usr/bin/python
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
from tkinter import *
from tkinter import filedialog
def collect():

	try:
		from tkinter import messagebox
		
		service_instance = connect.SmartConnectNoSSL(host=vcenter.get(),
														 user=username.get(),
														 pwd=password.get(),
														 port=port.get())
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
					vcenter.get()
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
		with open(ofile.get(),'w') as outfile:
			json.dump(output, outfile)
		messagebox.showinfo("Complete","Extraction is complete.")





	except vmodl.MethodFault as error:
		print("Caught vmodl fault : " + error.msg)
		return -1

def savefile():
	from tkinter import filedialog
	root.filename =  filedialog.asksaveasfilename(initialdir = ".",title = "Select file",filetypes = (("JSON files","*.json"),("all files","*.*")))
	ofile.insert(END, root.filename)
	



root = Tk()
root.title('NXO Collector')
root.grid_columnconfigure(3,pad=4)

logo = PhotoImage(file="NXOlogo.gif")
Label(root, text="").grid(row=0)
Label(root, text="vCenter Host", justify=LEFT, width=15).grid(row=1,sticky=W)
Label(root, text="Port", justify=LEFT, width=15).grid(row=5,sticky=W)
Label(root, text="Username", justify=LEFT, width=15).grid(row=3,sticky=W)
Label(root, text="Password", justify=LEFT, width=15).grid(row=4,sticky=W)
Label(root, text="Output File", justify=LEFT, width=15).grid(row=2,sticky=W)
Label(root, image=logo, justify=CENTER).grid(row=0, column=0,columnspan=3)


vcenter = Entry(root,width=10)
vcenter.insert(END, 'a.b.c.d')
port = Entry(root,width=5)
port.insert(END, '443')
username = Entry(root,width=15)
username.insert(END, 'administrator@.....')
password = Entry(root, show= '*',width=15)
ofile = Entry(root, width=15)
vcenter.grid(row=1, column=1, sticky=W)
port.grid(row=5, column=1, sticky=W)
username.grid(row=3, column=1, sticky=W)
password.grid(row=4, column=1, sticky=W)
ofile.grid(row=2, column=1, sticky=W)

button_start = Button(root, text='Extract', width=15, command=collect).grid(row=1, column=2, sticky=W, pady=4)
button_start = Button(root, text='Select File', width=15, command=savefile).grid(row=2, column=2, sticky=W, pady=4)
button_quit = Button(root, text='Exit', width=15, command=root.destroy).grid(row=5, column=2, sticky=W, pady=4)

root.mainloop()