#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Imports
import glob
import os
import joblib
import numpy as np
import sklearn.preprocessing
import sklearn.model_selection
import sklearn.metrics
import sklearn.decomposition
import sklearn.linear_model
import sklearn.svm
import mne
import imblearn
import scipy.io

# Set environment variable so solve issue with parallel crash
# https://stackoverflow.com/questions/40115043/no-space-left-on-device-error-while-fitting-sklearn-model/49154587#49154587
os.environ["JOBLIB_TEMP_FOLDER"] = "/tmp"

# Define paths
path_in = "/mnt/data_dump/bocotilt/2_autocleaned/"
path_out = "/mnt/data_dump/bocotilt/3_decoding_data/erp/"

# Function that calls the classifications
def decode_timeslice(X_all, trialinfo, decoding_task):

    # Select X and y data
    X = X_all[decoding_task["trial_idx"], :]
    y = trialinfo[decoding_task["trial_idx"], decoding_task["y_col"]]

    # Init undersampler
    undersampler = imblearn.under_sampling.RandomUnderSampler(
        sampling_strategy="not minority"
    )

    # Init classifier
    clf = sklearn.svm.SVC(kernel="linear")

    # Set number of iterations
    n_iterations = 10

    # List for classifier performance and feature importances
    acc = []

    # Loop iterations
    for _ in range(n_iterations):

        # Undersample data
        X_undersampled, y_undersampled = undersampler.fit_resample(X, y)

        # Shuffle data after undersampling
        X_undersampled, y_undersampled = sklearn.utils.shuffle(
            X_undersampled, y_undersampled
        )

        # Scale data
        scaler = sklearn.preprocessing.StandardScaler()
        X_undersampled = scaler.fit_transform(X_undersampled)

        # Compress data
        pca = sklearn.decomposition.PCA(n_components=0.9, svd_solver="full")
        X_undersampled = pca.fit_transform(X_undersampled)

        # Get data for both classes
        X0 = X_undersampled[y_undersampled == 0, :]
        X1 = X_undersampled[y_undersampled == 1, :]

        # Set binsize
        binsize = 10

        # Determine number of bins
        n_bins_per_class = int(np.floor(X0.shape[0] / binsize))

        # Get number of features
        _, n_features = X0.shape

        # Arrays for bins
        X_binned_0 = np.zeros((n_bins_per_class, n_features))
        X_binned_1 = np.zeros((n_bins_per_class, n_features))

        # Binning. Create ERPs
        for row_idx, X_idx in enumerate(np.arange(0, X0.shape[0], binsize)[:-1]):
            X_binned_0[row_idx, :] = X0[X_idx : X_idx + binsize, :].mean(axis=0)
            X_binned_1[row_idx, :] = X1[X_idx : X_idx + binsize, :].mean(axis=0)

        # Iterate bins
        for bin_idx in range(n_bins_per_class):

            # Get test data, one occurence of each class.
            X_test = np.stack((X_binned_0[bin_idx, :], X_binned_1[bin_idx, :]))

            # Get test labels
            y_test = np.array((0, 1))

            # Shuffle test data
            X_test, y_test = sklearn.utils.shuffle(X_test, y_test)

            # Exclude test bins from binned data
            X_train_0 = np.delete(X_binned_0, bin_idx, 0)
            X_train_1 = np.delete(X_binned_1, bin_idx, 0)

            # Concatenate bins to training dataset
            X_train = np.concatenate((X_train_0, X_train_1), axis=0)

            # Create label vector
            y_train = np.concatenate(
                (np.zeros((n_bins_per_class - 1,)), np.ones((n_bins_per_class - 1,))),
                axis=0,
            )

            # Shuffle training data after bin creation
            X_train, y_train = sklearn.utils.shuffle(X_train, y_train)

            # Fit model
            clf.fit(X_train, y_train)

            # Get accuracy
            acc.append(sklearn.metrics.accuracy_score(y_test, clf.predict(X_test)))

    # Average
    average_acc = np.stack(acc).mean(axis=0)

    # This is important!
    return average_acc


# Get list of dataset
datasets = glob.glob(f"{path_in}/*cleaned.set")

# Iterate preprocessed datasets
for dataset_idx, dataset in enumerate(datasets):

    # Get subject id as string
    id_string = dataset.split("VP")[1][0:2]

    # Talk
    print(f"Decoding dataset {dataset_idx + 1} / {len(datasets)}.")

    # Set sampling rate
    srate = 200

    # Read channel labels as list
    channel_label_list = scipy.io.loadmat(os.path.join(path_in, "channel_labels.mat"))[
        "channel_labels"
    ][0].split(" ")[1:]

    # Rename channels to match standard montage info of MNE
    for x in range(len(channel_label_list)):
        if channel_label_list[x] == "O9":
            channel_label_list[x] = "OI1"
        if channel_label_list[x] == "O10":
            channel_label_list[x] = "OI2"

    # Load epoch data
    eeg_data = scipy.io.loadmat(dataset)["data"].transpose((2, 0, 1))

    # Create info struct
    eeg_info = mne.create_info(channel_label_list, srate)

    # Create epoch struct
    eeg_epochs = mne.EpochsArray(eeg_data, eeg_info, tmin=-1).decimate(2)

    # Create channel type mapping
    mapping = {}
    for x in channel_label_list:
        mapping[x] = "eeg"

    # Apply mapping
    eeg_epochs.set_channel_types(mapping)

    # Set montage
    montage = mne.channels.make_standard_montage("standard_1005")
    eeg_epochs.set_montage(montage)

    # Load trialinfo
    trialinfo = scipy.io.loadmat(dataset)["trialinfo"]

    # # Get indices of channels to pick
    # to_pick_labels = [
    #     "Fz",
    #     "F3",
    #     "F4",
    #     "Cz",
    #     "C3",
    #     "C4",
    #     "C5",
    #     "C6",
    #     "Pz",
    #     "P3",
    #     "P4",
    #     "P5",
    #     "P6",
    #     "OI1",
    #     "OI2",
    #     "POz",
    #     "PO3",
    #     "PO4",
    #     "PO7",
    #     "PO8",
    # ]
    # to_pick_idx = [eeg_epochs.ch_names.index(x) for x in to_pick_labels]

    # Save info object for plotting topos
    info_object = eeg_epochs.info

    # Prune in time
    to_keep_idx = (eeg_epochs.times >= -0.2) & (eeg_epochs.times <= 1.6)
    tf_times = eeg_epochs.times[to_keep_idx]
    tf_data = eeg_epochs.get_data()[:, :, to_keep_idx]  # Data is trial x channel x time

    # Clean up
    del eeg_epochs, eeg_data

    # Positions of target and distractor are coded  1-8, starting at the top-right position, then counting counter-clockwise

    # Recode distractor and target positions in 4 bins 0-3 (c.f. https://www.nature.com/articles/s41598-019-45333-6)
    # trialinfo[:, 19] = np.floor((trialinfo[:, 19] - 1) / 2)
    # trialinfo[:, 20] = np.floor((trialinfo[:, 20] - 1) / 2)

    # Recode distractor and target positions in 2 bins 0-1 (roughly left vs right...)
    trialinfo[:, 20] = np.floor((trialinfo[:, 20] - 1) / 4)
    trialinfo[:, 21] = np.floor((trialinfo[:, 21] - 1) / 4)

    # Exclude trials: Practice-block trials and first-of-sequence trials and no-response trials
    idx_to_keep = (
        (trialinfo[:, 1] >= 5)
        & (trialinfo[:, 22] > 1)
        & ((trialinfo[:, 13] > -1) & (trialinfo[:, 13] < 2))
    )
    trialinfo = trialinfo[idx_to_keep, :]
    tf_data = tf_data[idx_to_keep, :, :]

    # get dims
    n_trials, n_channels, _ = tf_data.shape

    # Trialinfo cols:
    # 00: id
    # 01: block_nr
    # 02: trial_nr
    # 03: bonustrial
    # 04: tilt_task
    # 05: cue_ax
    # 06: target_red_left
    # 07: distractor_red_left
    # 08: response_interference
    # 09: task_switch
    # 10: prev_switch
    # 11: prev_accuracy
    # 12: correct_response
    # 13: response_side
    # 14: rt
    # 15: rt_thresh_color
    # 16: rt_thresh_tilt
    # 17: accuracy
    # 18: position_color
    # 19: position_tilt
    # 20: position_target
    # 21: position_distractor
    # 22: sequence_position

    # A list for stuff to classify
    decoding_tasks = []

    # Bonus decoding
    decoding_tasks.append(
        {
            "label": "bonus_vs_standard_in_repeat",
            "trial_idx": trialinfo[:, 9] == 0,
            "y_col": 3,
        }
    )
    
    decoding_tasks.append(
        {
            "label": "bonus_vs_standard_in_switch",
            "trial_idx": trialinfo[:, 9] == 1,
            "y_col": 3,
        }
    )

    # Task decoding
    decoding_tasks.append(
        {
            "label": "task_in_repeat_in_standard",
            "trial_idx": (trialinfo[:, 9] == 0) & (trialinfo[:, 3] == 0),
            "y_col": 4,
        }
    )
    decoding_tasks.append(
        {
            "label": "task_in_repeat_in_bonus",
            "trial_idx": (trialinfo[:, 9] == 0) & (trialinfo[:, 3] == 1),
            "y_col": 4,
        }
    )
    
    decoding_tasks.append(
        {
            "label": "task_in_repeat_in_standard",
            "trial_idx": (trialinfo[:, 9] == 0) & (trialinfo[:, 3] == 0),
            "y_col": 4,
        }
    )
    decoding_tasks.append(
        {
            "label": "task_in_repeat_in_bonus",
            "trial_idx": (trialinfo[:, 9] == 0) & (trialinfo[:, 3] == 1),
            "y_col": 4,
        }
    )
    
    

    # Cue decoding
    decoding_tasks.append(
        {
            "label": "cue_in_standard_in_color",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 0),
            "y_col": 5,
        }
    )
    decoding_tasks.append(
        {
            "label": "cue_in_standard_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 1),
            "y_col": 5,
        }
    )
    decoding_tasks.append(
        {
            "label": "cue_in_bonus_in_color",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 0),
            "y_col": 5,
        }
    )
    decoding_tasks.append(
        {
            "label": "cue_in_bonus_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 1),
            "y_col": 5,
        }
    )

    # Response decoding
    decoding_tasks.append(
        {
            "label": "response_in_standard_in_color",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 0),
            "y_col": 13,
        }
    )
    decoding_tasks.append(
        {
            "label": "response_in_standard_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 1),
            "y_col": 13,
        }
    )
    decoding_tasks.append(
        {
            "label": "response_in_bonus_in_color",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 0),
            "y_col": 13,
        }
    )
    decoding_tasks.append(
        {
            "label": "response_in_bonus_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 1),
            "y_col": 13,
        }
    )

    # Target decoding
    decoding_tasks.append(
        {
            "label": "target_in_standard_in_color",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 0),
            "y_col": 20,
        }
    )
    decoding_tasks.append(
        {
            "label": "target_in_standard_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 1),
            "y_col": 20,
        }
    )
    decoding_tasks.append(
        {
            "label": "target_in_bonus_in_color",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 0),
            "y_col": 20,
        }
    )
    decoding_tasks.append(
        {
            "label": "target_in_bonus_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 1),
            "y_col": 20,
        }
    )

    # Distractor decoding
    decoding_tasks.append(
        {
            "label": "distractor_in_standard_in_color",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 0),
            "y_col": 21,
        }
    )
    decoding_tasks.append(
        {
            "label": "distractor_in_standard_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 0) & (trialinfo[:, 4] == 1),
            "y_col": 21,
        }
    )
    decoding_tasks.append(
        {
            "label": "distractor_in_bonus_in_color",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 0),
            "y_col": 21,
        }
    )
    decoding_tasks.append(
        {
            "label": "distractor_in_bonus_in_tilt",
            "trial_idx": (trialinfo[:, 3] == 1) & (trialinfo[:, 4] == 1),
            "y_col": 21,
        }
    )

    # Re-arrange data
    X_list = []
    temporal_smoothing = 3
    tf_times = tf_times[: -(temporal_smoothing - 1)]
    for time_idx, timeval in enumerate(tf_times):

        # Data as trials x channels x frequencies. Apply a temporal smoothing
        timepoint_data = tf_data[:, :, time_idx : time_idx + temporal_smoothing].mean(
            axis=2
        )

        # Trials in rows
        timepoint_data_2d = timepoint_data.reshape((n_trials, n_channels))

        # Stack data
        X_list.append(timepoint_data_2d)

    # Clean up
    del tf_data

    # Iterate classification-tasks
    for decoding_task in decoding_tasks:

        # Specify out file name for decoding task
        out_file = os.path.join(
            path_out, f"{decoding_task['label']}_{id_string}.joblib"
        )

        # Check if done already. If so -> skip
        if os.path.isfile(out_file):
            continue

        # Fit random forest
        out = joblib.Parallel(n_jobs=-2)(
            joblib.delayed(decode_timeslice)(X, trialinfo, decoding_task)
            for X in X_list
        )

        # Stack accuracies
        acc = np.stack([x for x in out])

        # Compile output
        output = {
            "id": id_string,
            "decode_label": decoding_task["label"],
            "times": tf_times,
            "acc": acc,
            "info_object": info_object,
        }

        # Save
        joblib.dump(output, out_file)
