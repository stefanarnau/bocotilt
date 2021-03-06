#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 27 17:35:36 2021

@author: plkn
"""

# Import
import joblib
import glob
import matplotlib.pyplot as plt
import numpy as np
import mne

# Path decoding data
path_in = "/mnt/data_dump/bocotilt/3_decoded/"

# Get list of datasets
datasets = glob.glob(f"{path_in}/*.joblib")

# Smoothin factor
smowin = 5

# A smoothening function
def moving_average(x, w=smowin):
    return np.convolve(x, np.ones(w), "valid") / w


# A plotting and statistics function
def plot_decoding_result(
    data_std_rep,
    data_std_swi,
    data_bon_rep,
    data_bon_swi,
    decode_label="title",
    f_thresh=6.0,
):

    # Average for main effects
    data_std = np.stack(
        [(data_std_rep[x] + data_std_swi[x]) / 2 for x in range(len(data_std_rep))]
    )
    data_bon = np.stack(
        [(data_bon_rep[x] + data_bon_swi[x]) / 2 for x in range(len(data_bon_rep))]
    )
    data_rep = np.stack(
        [(data_std_rep[x] + data_bon_rep[x]) / 2 for x in range(len(data_std_rep))]
    )
    data_swi = np.stack(
        [(data_std_swi[x] + data_bon_swi[x]) / 2 for x in range(len(data_std_swi))]
    )

    # Stack
    data_std_rep = np.stack(data_std_rep)
    data_std_swi = np.stack(data_std_swi)
    data_bon_rep = np.stack(data_bon_rep)
    data_bon_swi = np.stack(data_bon_swi)

    # Interaction data
    data_int_std = data_std_swi - data_std_rep
    data_int_bon = data_bon_swi - data_bon_rep

    # Test bonus
    (
        T_obs_bon,
        clusters_bon,
        cluster_p_values_bon,
        H0_bon,
    ) = mne.stats.permutation_cluster_test(
        [data_std, data_bon],
        n_permutations=1000,
        threshold=f_thresh,
        tail=1,
        n_jobs=1,
        out_type="mask",
    )

    # Test switch
    (
        T_obs_swi,
        clusters_swi,
        cluster_p_values_swi,
        H0_swi,
    ) = mne.stats.permutation_cluster_test(
        [data_rep, data_swi],
        n_permutations=1000,
        threshold=f_thresh,
        tail=1,
        n_jobs=1,
        out_type="mask",
    )

    # Test interaction
    (
        T_obs_int,
        clusters_int,
        cluster_p_values_int,
        H0_int,
    ) = mne.stats.permutation_cluster_test(
        [data_int_std, data_int_bon],
        n_permutations=1000,
        threshold=f_thresh,
        tail=1,
        n_jobs=1,
        out_type="mask",
    )
    print(cluster_p_values_int)
    # Create 2-axis figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 4))

    # Set figure title
    fig.suptitle(decode_label, fontsize=12)

    # Plot classifier performance
    ax1.plot(
        times, data_std_rep.mean(axis=0), label="std-rep",
    )
    ax1.plot(
        times, data_std_swi.mean(axis=0), label="std-swi",
    )
    ax1.plot(
        times, data_bon_rep.mean(axis=0), label="bon-rep",
    )
    ax1.plot(
        times, data_bon_swi.mean(axis=0), label="bon-swi",
    )

    ax1.set_ylabel("accuracy")
    ax1.set_xlabel("time (s)")
    ax1.legend()

    # Plot statistics
    for i_c, c in enumerate(clusters_int):
        c = c[0]
        if cluster_p_values_int[i_c] <= 0.05:
            ax1.axvspan(times[c.start], times[c.stop - 1], color="g", alpha=0.3)
        else:
            ax1.axvspan(
                times[c.start], times[c.stop - 1], color=(0.3, 0.3, 0.3), alpha=0.3
            )

    # hf = plt.plot(times, T_obs_bon, "m")
    # ax2.legend((h,), ("cluster p-value < 0.05",))
    ax2.set_xlabel("time (s)")
    ax2.set_ylabel("f-values")

    # Tight layout
    fig.tight_layout()


# Average across subjects
task_std_rep = []
task_std_swi = []
task_bon_rep = []
task_bon_swi = []
cue_std_rep = []
cue_std_swi = []
cue_bon_rep = []
cue_bon_swi = []
response_std_rep = []
response_std_swi = []
response_bon_rep = []
response_bon_swi = []
target_std_rep = []
target_std_swi = []
target_bon_rep = []
target_bon_swi = []
distractor_std_rep = []
distractor_std_swi = []
distractor_bon_rep = []
distractor_bon_swi = []

# read data
for dataset in datasets:

    # Load dataset
    data = joblib.load(dataset)

    # Task decoding
    task_std_rep.append(moving_average(data["acc"][0]))
    task_std_swi.append(moving_average(data["acc"][1]))
    task_bon_rep.append(moving_average(data["acc"][2]))
    task_bon_swi.append(moving_average(data["acc"][3]))

    cue_std_rep.append(moving_average(data["acc"][4]))
    cue_std_swi.append(moving_average(data["acc"][5]))
    cue_bon_rep.append(moving_average(data["acc"][6]))
    cue_bon_swi.append(moving_average(data["acc"][7]))

    response_std_rep.append(moving_average(data["acc"][8]))
    response_std_swi.append(moving_average(data["acc"][9]))
    response_bon_rep.append(moving_average(data["acc"][10]))
    response_bon_swi.append(moving_average(data["acc"][11]))

    target_std_rep.append(moving_average(data["acc"][12]))
    target_std_swi.append(moving_average(data["acc"][13]))
    target_bon_rep.append(moving_average(data["acc"][14]))
    target_bon_swi.append(moving_average(data["acc"][15]))

    distractor_std_rep.append(moving_average(data["acc"][16]))
    distractor_std_swi.append(moving_average(data["acc"][17]))
    distractor_bon_rep.append(moving_average(data["acc"][18]))
    distractor_bon_swi.append(moving_average(data["acc"][19]))


# Adjust time vector to smoothing function
times = data["tf_times"][smowin - 1 :]


# Plot
plot_decoding_result(
    task_std_rep,
    task_std_swi,
    task_bon_rep,
    task_bon_swi,
    decode_label="stuff",
    f_thresh=2.0,
)

