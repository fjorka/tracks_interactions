import os
import yaml

import importlib

import numpy as np
from skimage.measure import regionprops
from skimage.measure._regionprops import COL_DTYPES, _require_intensity_image

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from tracks_interactions.db.db_model import TrackDB, CellDB
import tracks_interactions.db.db_functions as fdb

def testConfigFile(file_path):
    """
    Test whether the config file is executable.
    """

    # load the config file
    with open(file_path, 'r') as config_file:
        try:
            config = yaml.safe_load(config_file)
        except yaml.YAMLError as exc:
            return False, 'Error loading the config file: {}'.format(exc)

    # test if the database path is correct
    if 'database' not in config:
        return False, 'The database path is missing in the config file.'
    else:
        database_path = config['database']['path']
        status, msg = test_database_connection(database_path)
        if status is False:
            return False, msg

    # test whether signal channels are provided
    if 'signal_channels' not in config:
        return False, 'No signal channels provided in the config file.'
    else:
        for ch in config['signal_channels']:
            if 'zarr' not in ch['path']:
                return False, 'Accepting only zarr files as signal channels.'

    # test requested regionprops functions without signals
    req_regionprops_no_signal = [x['function'] for x in config['cell_measurements'] if x['source']=='regionprops' and not 'channels' in x]
    if not all([x in COL_DTYPES.keys() for x in req_regionprops_no_signal]):
        return False, 'Requested regionprops functions without signals are not supported.'
    
    # test requested regionprops functions with signals
    req_regionprops_signal = [x['function'] for x in config['cell_measurements'] if x['source']=='regionprops' and 'channels' in x]
    if not all([x in _require_intensity_image for x in req_regionprops_signal]):
        return False, 'Requested regionprops functions with signals are not supported.'

    # test track_gardener functions
    req_tr_gard_functions = [x['function'] for x in config['cell_measurements'] if x['source']=='track_gardener']

    for f in req_tr_gard_functions:
        if not hasattr(fdb, f):
            return False, f'Requested Track Gardener function "{f}" is not implemented. Use a custom function instead.'
    
    # test custom functions
    req_custom_functions = [x for x in config['cell_measurements'] if not x['source']=='regionprops' and not x['source']=='track_gardener']
    for f in req_custom_functions:
        status, msg = load_function_from_path(f['source'],f['function'])
        if status is False:
            return False, msg
    
    # test unique measurements names
    status, output = check_unique_names(config)
    if status is False:
        return False, output
    
    # check that the requested signals are in the database
    engine = create_engine(f'sqlite:///{database_path}')
    session = sessionmaker(bind=engine)()
    example_cell = session.query(CellDB).first()
    signal_list = list(example_cell.signals.keys())
    for x in output:
        if x not in signal_list:
            return False, f'Requested signal "{x}" not present in the database.'

    # test that graphs request existing measurements
    req_graphs = [signal for x in config['graphs'] for signal in x['signals']]
    for g in req_graphs:
        if g not in output:
            return False, f'Requested graph for "{g}" not present in measurements.'
    
    return True, 'Config file is executable.'

def test_database_connection(database_path):
    """
    Test whether the database file is executable.
    """

    try:
        # Create the database engine
        engine = create_engine(f'sqlite:///{database_path}')
        # Initialize a session
        session = sessionmaker(bind=engine)()
        
        return True, "Database connection successful."
    except SQLAlchemyError as e:
        return False, f"Database connection failed: {e}"

def load_function_from_module(module_name, function_name):
    module = importlib.import_module(module_name)
    return getattr(module, function_name) 

def load_function_from_path(file_path, function_name):
    # Check if the file exists
    if not os.path.exists(file_path):
        return False, f"File '{file_path}' does not exist."

    # Load the module from the specified file path
    module_name = os.path.splitext(os.path.basename(file_path))[0]  # Extract module name from file
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    try:
        # Execute the module to load it
        spec.loader.exec_module(module)
        # Get the function
        func = getattr(module, function_name)
        return True, func  # Successfully loaded function
    except (FileNotFoundError, AttributeError) as e:
        return False, f"Function '{function_name}' could not be loaded from '{file_path}': {e}"

def check_unique_names(config):
    """
    Check that the names of the measurements are unique.
    """
    req_f = [x for x in config['cell_measurements']]
    name_list = []
    for f in req_f:

        if 'channels' in f.keys():
            for ch in f['channels']:
                if 'name' in f.keys():
                    name = ch + '_' + f['name']
                else:
                    name = ch + '_' + f['function']
                name_list.append(name)

        else:
            if 'name' in f.keys():
                name = f['name']
            else:
                name = f['function']
            
            name_list.append(name)

    if len(name_list) == len(set(name_list)):
        return True, name_list
    else:
        return False, 'Measurement names are not unique.'
    
def create_calculate_signals_function(config):
    """
    Function to generate for signal calculation based on the requirements in the configuration file.
    input:
        config: dictionary containing all configuration information
    output:
        calculate_cell_signals: function that calculates all signals for a given cell
    """

    ch_list = [x.get('name') for x in config['signal_channels']]

    if config.get('cell_measurements') is None:
        return None

    # regionprops with no signal
    reg_no_signal = [x['function'] for x in config['cell_measurements'] if x['source']=='regionprops' and not 'channels' in x]

    # regionprops with signal
    reg_signal = [x for x in config['cell_measurements'] if x['source']=='regionprops' and 'channels' in x]

    # track gardener implemented functions
    gardener_signal = [x for x in config['cell_measurements'] if x['source']=='track_gardener']

    # custom functions
    custom_signal = [x for x in config['cell_measurements'] if not x['source']=='track_gardener' and not x['source']=='regionprops']

    if len(reg_no_signal) == 0 and len(reg_signal) == 0 and len(gardener_signal) == 0 and len(custom_signal) == 0:
        return None

    #######################################################################################################################
    def calculate_cell_signals(cell,t,ch_data_list):
        """
        Function to calculate signals for every given cell.
        input:
            cell: cell object from regionprops
            ch_data_list: list of all channel data
        output:
            cell_dict: dictionary containing all measurements for the cell
        """

        # create an empty dictionary
        cell_dict = dict()

        #######################################################################################################################
        # add all measurements directly from regionprops
        for m in reg_no_signal:
            cell_dict[m] = cell[m]

        #######################################################################################################################
        # add all measurements from regionprops with channels
        if len(reg_signal) > 0:

            signal_cube = np.zeros((cell.bbox[2]-cell.bbox[0],cell.bbox[3]-cell.bbox[1],len(ch_list)),dtype=ch_data_list[0].dtype)
            for ind,ch in enumerate(ch_data_list):
                if ch.ndim == 3:
                    cell_signal = ch[t,cell.bbox[0]:cell.bbox[2],cell.bbox[1]:cell.bbox[3]]
                if ch.ndim == 2:
                    cell_signal = ch[cell.bbox[0]:cell.bbox[2],cell.bbox[1]:cell.bbox[3]]

                signal_cube[:,:,ind] = cell_signal

            result = regionprops(cell.image.astype(int),intensity_image=signal_cube)

            for m in reg_signal:
                for ch in m['channels']:
                    cell_dict[ch + '_' + m['name']] = result[0][m['function']][ch_list.index(ch)]
      

        #######################################################################################################################
        # add measurements from the track gardener
        # for simplicity we calculate for all the channels - may be revisited later
        if len(gardener_signal) > 0:
            for m in gardener_signal:
                f = load_function_from_module('tracks_interactions.db.db_functions', m['function'])
                result = f(cell,t,ch_data_list,kwargs = m)
                for ch in m['channels']:
                    cell_dict[ch + '_' + m['name']] = result[ch_list.index(ch)]


        #######################################################################################################################
        # add measurements from the custom functions
        if len(custom_signal) > 0:
            for m in custom_signal:
                f = load_function_from_path(m['source'], m['function'])
                result = f(cell,t,ch_data_list,kwargs = m)
                for ch in m['channels']:
                    cell_dict[ch + '_' + m['name']] = result[ch_list.index(ch)]

        return cell_dict

    return calculate_cell_signals