import os

# true_contributors_mixin.py

# This module defines a set of functions for aggregating contributor data across
# GitHub repositories in an organization. It mimics GitHub API logic originally
# implemented in JavaScript.

# Note: This translation assumes the surrounding framework (e.g., GitHub API
# client such as PyGithub or similar) is already available in the environment.

# For each function, docstrings and comments mirror the original JS annotations.

# This would likely be encapsulated in a class in real use:
# Example: class TrueContributorsMixin:

def _sort_by_contributions(a, b):
    if "contributions" not in a or "contributions" not in b:
        raise ReferenceError("Missing 'contributions' property.")
    if not isinstance(a["contributions"], int) or not isinstance(b["contributions"], int):
        raise TypeError("Contribution values must be integers.")
    return b["contributions"] - a["contributions"]

def _contributor_dict_to_arr(dictionary):
    if not dictionary:
        raise ReferenceError("Contributor dictionary is not defined.")
    array = list(dictionary.values())
    return sorted(array, key=lambda x: x["contributions"], reverse=True)

def _reduce_contributors(contributor_dict, contributor):
    if "contributions" not in contributor or "id" not in contributor:
        raise ReferenceError(f"Invalid contributor entry: {contributor}")
    if contributor["id"] in contributor_dict:
        contributor_dict[contributor["id"]]["contributions"] += contributor["contributions"]
    else:
        contributor_dict[contributor["id"]] = contributor.copy()
    return contributor_dict

def _aggregate_contributors(contributors):
    result_dict = {}
    for c in contributors:
        result_dict = _reduce_contributors(result_dict, c)
    return _contributor_dict_to_arr(result_dict)

def _aggregate_contributions(contributions, key):
    if not key:
        raise ReferenceError("No contribution key provided.")
    filtered = [
        {**c[key], "contributions": 1}
        for c in contributions if key in c and c[key]
    ]
    return _aggregate_contributors(filtered)

def _create_params_from_object(desired_keys, input_dict):
    return {k: input_dict[k] for k in desired_keys if k in input_dict and input_dict[k]}

