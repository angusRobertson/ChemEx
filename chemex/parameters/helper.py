import ast
import itertools as it

import asteval.astutils as aa
import lmfit as lf

import chemex.nmr.rates as cnr
import chemex.parameters.kinetics as cpk
import chemex.parameters.liouvillian as cpl
import chemex.parameters.name as cpn
import chemex.parameters.settings as cps


def merge(params_list):
    params_ = {}
    for params in params_list:
        for name, param in params.items():
            if name in params_ and params_[name].vary:
                continue
            params_[name] = param
    params = lf.Parameters(usersyms=cnr.rate_functions)
    params.add_many(*params_.values())
    return params


def create_params(config, propagator):
    basis = config["basis"]
    model = config["model"]
    conditions = config["conditions"]
    spin_system = config["spin_system"]
    observed_state = config["experiment"]["observed_state"]

    # Get settings for kinetic parameters
    settings_k = cpk.make_settings[model.name](conditions, spin_system)

    # Get settings for the other parameters
    settings_l, settings_mf_l = cpl.make_settings(basis, model, conditions)
    _set_to_fit(settings_l, model, observed_state, config["fit"]["rates"])
    _set_to_fit(settings_mf_l, model, observed_state, config["fit"]["model_free"])

    # Create standard parameters from settings
    settings = {**settings_k, **settings_l}
    settings_min, settings_max = _get_settings(settings, propagator)
    pnames = cpn.get_pnames(settings_min, conditions, spin_system)
    params = _settings_to_params(settings_max, conditions, spin_system)

    # Create standard parameters from settings including model free parameters
    settings_mf = {**settings_k, **settings_mf_l}
    _, settings_mf_max = _get_settings(settings_mf, propagator)
    params_mf = _settings_to_params(settings_mf_max, conditions, spin_system)

    # Initialize parameters values using the parameter.toml file
    cps.set_values(params_mf, config["defaults"])
    if model.model_free:
        params = params_mf
    else:
        for pname in set(params) & set(params_mf):
            params[pname].value = params_mf[pname].value
        cps.set_values(params, config["defaults"])

    return pnames, params


def _settings_to_pnames(settings, conditions, propagator, spin_system):
    settings_profile = {k: settings[k] for k in set(settings) & set(propagator.snames)}
    return cpn.get_pnames(settings_profile, conditions, spin_system)


def _settings_to_params(settings, conditions, spin_system):
    pnames = cpn.get_pnames(settings, conditions, spin_system)
    parameter_list = [
        lf.Parameter(
            name=pnames[name],
            value=setting.get("value"),
            min=setting.get("min"),
            max=setting.get("max"),
            vary=setting.get("vary"),
            expr=setting.get("expr", "").format_map({**pnames, **conditions}),
        )
        for name, setting in settings.items()
    ]
    params = lf.Parameters(usersyms=cnr.rate_functions)
    params.add_many(*parameter_list)
    return params


def _get_settings(settings_full, propagator):
    settings_profile = {
        k: v for k, v in settings_full.items() if k in propagator.snames
    }
    settings_params = {}
    for name, setting in settings_profile.items():
        settings_params[name] = setting.copy()
        names_expr = aa.get_ast_names(ast.parse(setting.get("expr", "")))
        settings_params.update(
            {k: settings_full[k].copy() for k in names_expr if k in settings_full}
        )
    return settings_profile, settings_params


def _get_expr_names(expr):
    return aa.get_ast_names(ast.parse(expr))


def _set_to_fit(settings, model, observed_state, fitted):
    for sname, state in it.product(fitted, model.states):
        sname_ = sname.format(states=state, observed_state=observed_state)
        if sname_ in settings:
            settings[sname_]["vary"] = True
            settings[sname_]["expr"] = ""
