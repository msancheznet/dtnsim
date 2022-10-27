import sys
sys.path.append('../')

import numpy as np
import os
import pandas as pd
from pathlib import Path
import shutil
from simulator.utils.DtnIO import load_traffic_file
import traceback
import unittest
import warnings
import yaml

# Get to the right directory
base_dir = './' if 'tests' in os.getcwd() else './tests/'

def _run_test(test_id):
    # Load the config file
    with open(base_dir + f'test_{test_id}.yaml') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # Run the simulation (avoid circular import)
    from bin.main import run_simulation
    run_simulation(config=config)

    return config

class BasicTests(unittest.TestCase):
    """ Class that defines all tests """
    def test_1(self):
        # Run the test
        config = _run_test(1)

        # Compare if data volume matches
        self.compare_file_and_voice_dv(base_dir + 'results/test_1.h5', config)

    def test_2(self):
        # Run the test
        config = _run_test(2)

        # Compare if data volume matches
        self.compare_file_and_voice_dv(base_dir + 'results/test_2.h5', config)

    def test_3(self):
        # Run the test
        config = _run_test(3)

        # Compare if data volume matches
        self.compare_file_and_voice_dv(base_dir + 'results/test_3.h5', config)

    def test_4(self):
        # Run the test
        config = _run_test(4)

        # Compare if data volume matches
        self.compare_file_dv(base_dir + 'results/test_4.h5', config)

    def test_5(self):
        # Run the test
        config = _run_test(5)

        # Compare if data volume matches
        self.compare_file_dv(base_dir + 'results/test_5.h5', config)

    def test_6(self):
        # Run the test
        config = _run_test(6)

        # Compare if data volume matches
        self.compare_file_and_voice_dv(base_dir + 'results/test_6.h5', config)

    def test_7(self):
        # Run the test
        config = _run_test(7)

        # Compare if data volume matches
        self.compare_file_and_voice_dv(base_dir + 'results/test_7.h5', config)

    def test_9(self):
        # Run the test
        config = _run_test(9)

        # Compare if data volume matches
        self.compare_file_dv_test_9(base_dir + 'results/test_9.h5', config)

    def test_static_router(self):
        # Run the test
        config = _run_test('static_router')

        # Compare if data volume matches
        self.compare_static_routing_dv(base_dir + 'results/test_static_router.h5', config)

    def compare_file_and_voice_dv(self, file, config):
        # Compute the data volume from the two generators
        df = pd.read_hdf(file, '/arrived')
        dv = df.groupby('data_type').data_vol.sum()

        # Get the true amount of data that should be sent
        dv_voice = config['voice_generator']['rate'] * config['voice_generator']['until']

        # Do data volume tests. No data should be lost
        self.assertAlmostEqual(dv.voice, dv_voice, places=0)

    def compare_file_dv(self, file, config):
        # Compute the data volume from the two generators
        df = pd.read_hdf(file, '/arrived')
        dv = df.groupby('data_type').data_vol.sum()

        # Get information about the file generator
        Lfile = config['file_generator']['size']
        Lbnd  = config['file_generator']['bundle_size']
        Lblk  = config['multiband_duct']['agg_size_limit']

        # Get number of bundles to transmit file
        N1 = np.ceil(Lfile / Lbnd)

        # Get number of bundles per block
        N2 = np.ceil(Lblk / Lbnd)

        # Get number of bundles that will not be sent because
        # you cannot form a block
        dN = N1 - np.floor(N1 / N2) * N2

        # Do data volume tests. No data should be lost.
        self.assertAlmostEqual(dv.file, Lfile, delta=(dN + 1e-6) * Lbnd)

    def compare_file_dv_test_9(self, file, config):
        # Compute the data volume from the two generators
        df = pd.read_hdf(file, '/arrived')
        dv = df.groupby('data_type').data_vol.sum()

        # Get information about the file generator
        Lfile = config['file_generator']['size']

        # Do data volume tests. No data should be lost.
        # Note: Assume that there could be 3 order of magnitude difference
        # due to small bundles not being sent at the of simulation
        self.assertAlmostEqual(dv.file, Lfile, delta=Lfile/1000)

    def compare_static_routing_dv(self, file, config):
        # Compute the data volume from the two generators
        df = pd.read_hdf(file, '/arrived')
        dv = df.groupby(['orig','dest','data_type']).data_vol.sum()

        # Get the true amount of data that should be sent
        dv_voice = config['voice_generator1']['rate']*config['voice_generator1']['until']
        dv_file1 = config['file_generator1']['size']
        dv_file2 = config['file_generator4']['size']

        # Do data volume tests. No data should be lost
        self.assertAlmostEqual(dv.loc[('N1', 'N3', 'voice')], dv_voice, places=0)
        self.assertAlmostEqual(dv.loc[('N1', 'N2', 'file')],  dv_file1, places=0)
        self.assertAlmostEqual(dv.loc[('N4', 'N1', 'file')],  dv_file2, places=0)

class WalkerConsTests(unittest.TestCase):
    def test_network(self):
        # Run the simulation
        config = _run_test('walker_cons')

        # Get the output and validation files
        path  = Path(config['globals']['outdir'])
        ofile = path / config['globals']['outfile']
        vfile = path.parent/'validation'/config['globals']['outfile']

        # Tables to validate
        tables = ['sent', 'dropped', 'arrived']

        # Compare each table
        for table in tables:
            # Load tables from memory
            df1 = pd.read_hdf(ofile, key=table)
            df2 = pd.read_hdf(vfile, key=table)

            # Perform basic test. Shape of data frames needs
            # to be the same
            self.assertTrue(df1.shape == df2.shape,
                            msg=f'Check Table "{table}"')

            # Check that the arrived data volume matches
            self.assertAlmostEqual(df1.data_vol.sum(),
                                   df2.data_vol.sum())

class MobilityTests(unittest.TestCase):
    def test_epidemic_router(self):
        # Run the test
        config = _run_test('epidemic_routing')

def get_test_suite():
    # Create a suite of tests
    suite = unittest.TestSuite()

    # Add tests to the suite
    suite.addTest(BasicTests('test_1'))
    suite.addTest(BasicTests('test_2'))
    suite.addTest(BasicTests('test_3'))
    suite.addTest(BasicTests('test_4'))
    suite.addTest(BasicTests('test_5'))
    suite.addTest(BasicTests('test_6'))
    suite.addTest(BasicTests('test_7'))
    suite.addTest(BasicTests('test_9'))
    suite.addTest(BasicTests('test_static_router'))
    suite.addTest(WalkerConsTests('test_network'))
    #suite.addTest(MobilityTests('test_epidemic_router'))

    return suite

def run_tests(verbosity=5):
    # Disable python warnings
    warnings.simplefilter("ignore")

    # Get the tests suite
    suite = get_test_suite()

    # Reset the results folder
    shutil.rmtree(base_dir + 'results')
    os.makedirs(base_dir + 'results')

    # Run all tests
    unittest.TextTestRunner(verbosity=verbosity).run(suite)

if __name__ == '__main__':
    run_tests()
