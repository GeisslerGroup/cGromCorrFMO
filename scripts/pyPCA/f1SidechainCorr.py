import numpy as np
import csv 
import cPickle
import h5py
import sys
import matplotlib.pylab as plt
import argparse
import ConfigParser
from copy import deepcopy

h5crtag = "corr_ij"
h5eavtag = "eav_ij"
h5detag = "deltaseries_tia"
h5mstag = "modeseries_tia"


def SidechainRead(filename, cutoff = 3):
	dE_t_i = []
	counter = 0;
	times = 0;
	with open(filename,'r') as f:
		read = csv.reader(f)

		dE_i = []
		myArr = []

		for pos, csvline in enumerate(read):
			myArrOld = myArr
			myArr = np.array([float(x) for x in csvline])
			dE_i.append(myArr)
			if times >= cutoff:
				break
			counter += 1
			if (counter == 7):
				counter = 0;
				times = times + 1;
				dE_t_i.append(np.array(dE_i))
				dE_i = []
	return np.array(dE_t_i), times

def SidechainReadv2(filename, t_start = 0, t_end = 3):
	dE_t_i = []
	counter = 0;
	times = 0;
	with open(filename,'r') as f:
		read = csv.reader(f)

		dE_i = []
		myArr = []

		for pos, csvline in enumerate(read):
			if times >= t_start:
				myArrOld = myArr
				myArr = np.array([float(x) for x in csvline])
				dE_i.append(myArr)
			if times >= t_end:
				break
			counter += 1
			if (counter == 7):
				if times >= t_start:
					dE_t_i.append(np.array(dE_i))
					dE_i = []
				counter = 0;
				times = times + 1;
	return np.array(dE_t_i), times


def AvgAndCorrelateSidechains(E_t_ia, fEnd = 3, fStart = 0):
        assert(fStart < fEnd)
	numFrames = min(fEnd-fStart, E_t_ia.shape[0]-fStart)
        fEnd = fStart + numFrames
   
        num_chromo = E_t_ia.shape[1]
        num_vars   = E_t_ia.shape[2]
        Corr_i_ab = np.zeros( (num_chromo, num_vars, num_vars))
        
        
        for i in xrange(num_chromo):
            print "Computing covariance on chromophore number {}".format(i+1)
            print "\tArray size: ({},{})".format(E_t_ia.shape[2], E_t_ia.shape[0])
            max_floats = 4E9 / 8
            max_times = max_floats / E_t_ia.shape[2]
            chunks = int(np.ceil(E_t_ia.shape[0] / max_times))
            chunk_size = E_t_ia.shape[0]/chunks
            print "\tDesired number of chunks (assuming 4GB RAM usage): {}, Chunk size: {}, Missing Datapoints: {}".format(chunks, chunk_size, E_t_ia.shape[0] - (chunk_size * chunks))
            print "\tWARNING: No chunks being used currently"
            Corr_i_ab[i,:,:] = np.cov( E_t_ia[fStart:fEnd,i,:], rowvar=0 )

        print "Computing sums across all chromophpores..."
        AvgEia  = np.zeros( (num_chromo, num_vars) )
        for i in xrange(num_chromo):
            AvgEia[i,:]  = E_t_ia[fStart:fEnd,i,:].sum(axis=0)
            AvgEia[i,:]  /= numFrames

	##AvgEiaEib = np.array( [ np.tensordot(E_t_ia[fStart:fEnd,i,:], E_t_ia[fStart:fEnd,i,:], axes=(0,0)) for i in xrange(E_t_ia.shape[1]) ] )
        ##for i in xrange(num_chromo):
        ##    for a in xrange(num_vars):
        ##        print a
        ##        for b in xrange(num_vars):
        ##            AvgEiaEib = np.mean( E_t_ia[:,i,a]  * E_t_ia[:,i,b] )
	##Corr_i_ab = AvgEiaEib - np.einsum('...j,...k',AvgEia,AvgEia)

	return Corr_i_ab, AvgEia


def main():
        parser = argparse.ArgumentParser(description = 'Program to compute same-time correlation PCA for csv or hdf5 data, and save the correlation matrix out to file for use in other pyPCA modules')
        parser.add_argument('-num_frames', default=0, type=int,help='Number of frames to use for the corrlelation (Note: default and 0 mean all frames after offset)')
        parser.add_argument('-frame_offset', default=0, type=int,help='Number of frames to skip before beginning corrlelation')
        args = parser.parse_args()

	config = ConfigParser.RawConfigParser()
	config.read('./f0postProcess.cfg')


	h5file = config.get('sidechain','h5file')
	h5stats= config.get('sidechain','h5stats')
	corr_h5tag = config.get('sidechain','corr_h5tag')
	time_h5tag = config.get('sidechain','time_h5tag')

        t_start = args.frame_offset
        t_end   = args.num_frames + t_start

        with h5py.File(h5file,'r') as f:
            E_t_ia = f[time_h5tag]
            print E_t_ia.shape
            if args.num_frames == 0:
                t_end = E_t_ia.shape[0]
	    print "Computing same-time spatial correlations across {} time samples...".format(t_end-t_start)
            args.dt = E_t_ia.attrs['dt']
	    corr_iab,Avg_Eia = AvgAndCorrelateSidechains(E_t_ia, t_end, t_start)
	print "Database read closed..."
	print "Database append beginning..."
	with h5py.File(h5stats,'w') as f:
		try:
			print "\tSaving to "+corr_h5tag+h5crtag+" correlation matrix of shape",corr_iab.shape,"..."
			crdset = f.require_dataset(corr_h5tag+h5crtag, corr_iab.shape, dtype='f');
			crdset[...] = corr_iab
                        crdset.attrs['dt'] = args.dt
                        crdset.attrs['tstart'] = t_start
                        crdset.attrs['tend']   = t_end
			# Store the time-average at each site
			print "\tSaving to "+corr_h5tag+h5eavtag+" averages of shape",Avg_Eia.shape,"..."
			eavdset = f.require_dataset(corr_h5tag+h5eavtag, Avg_Eia.shape, dtype='f');
			eavdset[...] = Avg_Eia
                        eavdset.attrs['dt'] = args.dt
                        eavdset.attrs['tstart'] = t_start
                        eavdset.attrs['tend']   = t_end
	
		except TypeError:
			print "\n\nERROR: Error in write encountered, you should consider changing the h5_tag to a value that has not been used."
			raise

	print "Database closed"


if __name__ == "__main__":
	main()
