from __future__ import absolute_import
import importlib

import os
import numpy as np

from chemex.experiments.cest import util


def read_profiles(path, profile_filenames, experiment_details, res_incl=None, res_excl=None):
    experiment_type = experiment_details['type']
    experiment_details['experiment_name'] = name_experiment(experiment_details)
    experiment_module = importlib.import_module('.'.join(['chemex.experiments', experiment_type]))

    Profile = getattr(experiment_module, 'Profile')

    dtype = [
        ('b1_offsets', '<f8'),
        ('intensities', '<f8'),
        ('intensities_err', '<f8')
    ]

    profiles = []

    for profile_name, filename in profile_filenames.items():
        full_path = os.path.join(path, filename)
        measurements = np.loadtxt(full_path, dtype=dtype)
        profile = Profile(profile_name, measurements, experiment_details)
        profiles.append(profile)

    error = experiment_details.get('error', 'file')
    if error not in {'file', 'auto'}:
        print('Warning: The \'error\' option should either be \'file\' or \'auto\'. Set to \'file\'')
        error = 'file'

    if error == 'auto':

        for profile in profiles:
            error_value = util.estimate_noise(profile.val[profile.b1_offsets >= -10000.0])
            profile.err = np.zeros_like(profile.err) + error_value

    if res_incl is not None:
        profiles = [profile for profile in profiles if profile.profile_name in res_incl]
    elif res_excl is not None:
        profiles = [profile for profile in profiles if profile.profile_name not in res_excl]

    ndata = sum(len(profile.val) for profile in profiles)

    return profiles, ndata


def name_experiment(experiment_details=None):
    if experiment_details is None:
        experiment_details = dict()

    if 'name' in experiment_details:
        name = experiment_details['name'].strip().replace(' ', '_')

    else:
        exp_type = experiment_details['type'].replace('.', '_')
        h_larmor_frq = float(experiment_details['h_larmor_frq'])
        temperature = float(experiment_details['temperature'])
        b1_frq = float(experiment_details['b1_frq'])
        time_t1 = float(experiment_details['time_t1'])

        name = '{:s}_{:.0f}Hz_{:.0f}ms_{:.0f}MHz_{:.0f}C'.format(
            exp_type,
            b1_frq,
            time_t1 * 1e3,
            h_larmor_frq,
            temperature
        ).lower()

    return name
