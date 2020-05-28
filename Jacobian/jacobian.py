"""
Helper Functions to compute the spectrum of J^T @ J and J @ J^T, 
were J is the Jacobian of the Neural Network J = df(x)/dx as a function of it's input (the data, not the weights).
We clarify some nomenclature. The diagonal Jacobian is constructed of terms only of the form dJ(x_i)/dx_i. 
It will be of dimension training_data_size*(output_dim*data_dim). The full J will contains terms of the form 
dJ(x_i)/dx_j, which will be of dimension training_data_size*(output_dim*training_data_size*data_dim)
The diagonal OF M = J @ J^T or M = J^T @ J is the main diagonal of M.
"""

import torch
from torch.autograd.gradcheck import zero_gradients
import numpy as np
import math

def batch_diagJ(inputs, output):
	"""
	input: input for the function for which the Jacobian will
	computed. It will be batch_size*data_dim. Make sure that the
	input is flagged as requires_grad=True with the torch.autograd.Variable
	wrapper. 

	output: output of the function for which the Jacobian will
	be computed. It will be batch_size*classes

	return: Jacobian of dimension batch_size*classes*data_dim
	"""
	assert inputs.requires_grad

	num_classes = output.size()[1] #0 index is batch

	jacobian = torch.zeros(num_classes, *inputs.size())
	grad_output = torch.zeros(*output.size())
	if inputs.is_cuda:
		grad_output = grad_output.cuda()
		jacobian = jacobian.cuda()

	#zero out gradients
	#compute gradient for one of the classes
	for i in range(num_classes):
		zero_gradients(inputs)
		grad_output.zero_()
		grad_output[:,i] = 1
		output.backward(grad_output, retain_graph=True)
		jacobian[i] = inputs.grad.data

	return torch.transpose(jacobian, dim0=0, dim1=1)

def construct_diagJ(model, data_loader, batch_size, device='cuda:0', num_classes=10, data_dim = 3*32*32):
	"""
	constructs the diagonal J matrix from batches.

	input: model, data_loader, batch_size, device, num_classes, data_dim

	optional arguments: device, num_classes (default 10), data_dim (default: 3072)

	output: diagonal Jacobian of dimension (len(data_loader)*batch_size, num_classes*data_dim)

	"""
	Js = []
	model.eval()
	model = model.to(device)

	for batch, data in enumerate(data_loader):
		features, _ = data

		inputs = features.to(device)
		inputs.requires_grad=True
		outputs = model(inputs)

		J = batch_diagJ(inputs, outputs)

		Js.append(J)

	full_J = torch.stack(Js, dim=0)
	full_J = full_J.reshape(len(data_loader)*batch_size, num_classes*data_dim)

	return full_J

def diagonal_JJT(model, data_loader, batch_size, num_classes=10, device='cuda:0', data_dim=3*32*32):
	"""
	Compute the main diagonal of JJ^T, where J is the diagonal Jacobian.

	input: model, data_loader, batch_size

	optional arguments: num_classes (default: 10), device (default: cuda:0), data_dim (default: 3072)

	return: Array of len(data_loader)*batch_size with the main diagonal of JJ^T.

	"""


	Jdiag = []
	model = model.to(device)

	for batch, data in enumerate(data_loader):
		features, _ = data
		features = features.to(device)

		features = torch.autograd.Variable(features, requires_grad=True)
		out = model(features)

		J = compute_jacobian(features, out)# create_graph=True)
		J = J.reshape(batch_size,num_classes*data_dim)
		Jt = J.clone().transpose_(0,1)
		batch_diag = torch.mm(J,Jt).to('cpu') #
		del J, Jt
		torch.cuda.empty_cache()

	for ib in range(batch_size):
		Jdiag.append(batch_diag[ib, ib].to('cpu').numpy())

	del batch_diag

	torch.cuda.empty_cache()

	return np.array(Jdiag)

def sketch_JL_JJT(J, dim=5000):
	"""
	Creates a Johnson-Lindenstrauss sketch of J of dimension dim, and computes M = J @ JT.

	Input: Jacobian, J

	Optional: dim (default: 5000)

	Return: M = PJ @ (PJ)^T, were P is a JL matrix.

	"""
	n, _ = J.shape

	P = 1/dim*torch.empty(dim, n).normal_(mean=0,std=1.)

	P_J = P @ J

	M = P_J @ P_J.t()

	del P_J

	return M

def power_method(M, iterations=100, device="cuda:0"):
	"""
	Computes the top eigenvalue of a matrix. This needs to be computed for kernel PM.

	input: the jacobian correlation matrix, M

	optional: iterations (default: 100), device (default: cuda:0)

	return: the largest eigenvalue of M.
	"""
	n, _ = M.shape

	#M = M.to(device)
	vk = torch.empty(n, device=device).normal_(mean=0, std=1.)

	for i in range(iterations):
		vk1 = M @ vk
		vk1_norm = torch.norm(vk1)
		vk = vk1 / vk1_norm

	top_eig = vk @ M @ vk

	del vk
	del vk1

	return top_eig

def SLQ(M, n_vec=20, m=100):
	"""
	An implemention of the Stochastic Lanczos Quadrature to compute
	the spectral density of M = JJ^T.
	input: the correlation matrix of the Jacobian M.
	optional: number of random vectors, n_vec (default: 20)
	number of iterations, m (default: 100)
	output: density of states.
	"""

	n, _ = M.shape




	for k in range(n_vec):

		v = torch.randint(low=0, high=2, size=n)
		v[v == 0] = -1
		v = v/torch.norm(v)

		alphas = torch.zeros(m)
		betas = torch.zeros(m)

		for i in range(m):

			if i == 0:
				
				w = M @ v
				a = w @ v
				w = w - a @ v
				v_j1 = v

				alphas[i] = a

			else:
				b = torch.norm(w)

				if b ! = 0:
					v = w/b
				else:
					#whp new v is orthogonal to others
					v = torch.randint(low=0, high=2, size=n)
					v[v==0] = -1 #make it rademacher
					v = v/torch.norm(v)

				w = M @ v
				a = w @ v
				w = w - a @ v - b*v_j1

				alphas[i] = a
				betas[i] = b #there is no beta 0
		
		#alphas has m entries
		#betas has m-1 entries (0 index is 0)
		#Construct T and diagonalize with symeig
		#create phi

	#average over phis

	return phi

def kernel_PM(M, m= 20, n_vec=100, device="cuda:0", power_it=100):
	"""
	An implementation of the Kernel Polynomial Method as outlined in Lin, Saad, Yaang.
	
	input: jacobian correlation matrix M. Degree of Chebyshev expansion, m.
	
	Optional: number of random vectors, n_vec (default:100), device (default: cuda:0), power_it (default: 100)

	output: coefficients for the chebyshev expansion, mu. They are the coefficients for the Chebyshev series
	1/sqrt(1-t^2)sum_k mu_k T_k(t).
	"""

	n, _ = M.shape

	a = 0 #smallest eigenvalue of M
	print("Computing top eigenvalue.")

	# We want to compute the power method on the GPU

	vk = torch.empty(n, device=device).normal_(mean=0, std=1.)

	for i in range(power_it):
		vk1 = M @ vk
		vk1_norm = torch.norm(vk1)
		vk = vk1 / vk1_norm

	b = vk @ M @ vk

	del vk
	del vk1

	M = M.to("cpu")

	torch.cuda.empty_cache()

	print("Finished top eigenvalue, computing mu")

	# We want to rescale M = (M - ((b + a)/2)*I)/((b-a)/2). M needs to be rescaled for Chebyshev basis
	# This is done in a for loop so I does not need to be made in memory.

	print("Rescaling M")
	for i in range(n):
	    M[i][i] = M[i][i] - (b+a)/2
	
	# This is done on the cpu, as you need a 2*size(M) to do this
	M = M/((b-a)/2)
	print("Done Rescaling M")

	M = M.to(device) #send M to gpu.

	zeta = torch.zeros(m, device = device)
	mu = torch.zeros(m, device = device)

	for l in range(n_vec): #number of vecs

		print("Iteration {} of computing mu".format(l))
		v0 = torch.empty(n, device=device).normal_(mean=0, std=1.)

		for k in range(m): #cheby degree
			if k == 0:
				zeta[k] = zeta[k] + v0 @ v0
				vk = M @ v0

			elif k == 1:
				zeta[k] = zeta[k] + v0 @ vk
				# vk = 2* M @ vk - vk
				# Need to break up computation to fit on GPU
				tmp = M @ vk #- vk
				tmp = 2*tmp
				vk1 = vk
				vk = tmp - v0
				del tmp
			else:
				zeta[k] = zeta[k] + v0 @ vk
				tmp = M @ vk #- vk
				tmp = 2*tmp
				p = vk
				vk = tmp - vk1
				vk1 = p
				del tmp
				del p

		del v0
	#del M

	zeta = zeta/n_vec
	for k in range(m):
		if k == 0:
			mu[k] = 1/(n*math.pi)*zeta[k]
		else:
			mu[k] = 2/(n*math.pi)*zeta[k]

	return mu

#
