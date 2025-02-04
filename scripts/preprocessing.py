"""
Preprocessing
_________________________________________________________________________________________________
This is where the data pre-processing will go
"""

import os
import uproot
import numpy as np
import glob
from sklearn.preprocessing import StandardScaler
import numba as nb
import matplotlib.pyplot as plt
from tensorflow.keras.layers.experimental import preprocessing


class Reweighter:
    """
    This class computes the pT re-weighting coefficients by making histograms of TauJets.pt for both jets and taus. 
    The re-weighting coefficient is the ratio of the tau / jet histograms
    TODO: Make it so that the directories and cuts are not hardcoded
    """

    def __init__(self, ntuple_dir, prong=None):
        tau_files = glob.glob(os.path.join(ntuple_dir, "*Gammatautau*", "*.root"))
        jet_files = glob.glob(os.path.join(ntuple_dir, "*JZ*", "*.root"))

        assert len(tau_files) != 0 and len(jet_files) != 0, "The Reweighter found no files! Please check file path to NTuples"

        jet_cuts = "(TauJets.ptJetSeed > 15000.0) & (TauJets.ptJetSeed < 10000000.0)"
        tau_cuts = jet_cuts
        if prong is not None:
            tau_cuts = f"(TauJets.truthProng == {prong}) & " + jet_cuts 

        variable = "TauJets.ptJetSeed"
        tau_data = uproot.concatenate(tau_files, filter_name=variable, cut=tau_cuts, library='np')
        jet_data = uproot.concatenate(jet_files, filter_name=variable, cut=jet_cuts, library='np')

        jet_pt = jet_data[variable]
        tau_pt = tau_data[variable]

        # Binning
        xmax = max([np.amax(tau_pt), np.amax(jet_pt)])
        xmin = min([np.amin(tau_pt), np.amin(jet_pt)])
        bin_edges = np.linspace(xmin, xmax, 1000)

        """
        Need to use the bin centres as weights rather than the bin edges! Otherwise you get imperfect pT re-weighting!
        Use plt.hist rather than np.histogram for this
        """

        plt.ioff()  # Disable interactive plotting so we don't see anything
        fig = plt.figure()
        tau_hist, _, _ = plt.hist(tau_pt, bins=bin_edges)
        jet_hist, _, _ = plt.hist(jet_pt, bins=bin_edges)
        plt.close(fig)  # Close figure so that it doesn't interfere with future plots

        # Reweighting coefficient
        self.coeff = np.where(jet_hist > 0, tau_hist / (jet_hist + 1e-12), 1)
        self.bin_edges = bin_edges

    def reweight(self, jet_pt, strides=None):
        """
        Get an array of weights from an array of jet pTs. One weight is asigned per jet. For plotting re-weighted
        histograms of  nested data e.g. TauTracks.pT etc... use the strides option.
        :param jet_pt: Array of TauJets.pt
        :param strides: An array containing the multiplicity of the object for each jet. E.g. [4, 5, 10, 0 ...] for a
        set of jets where; the 1st jet has 4 tracks, the second 5, the third 10, the fourth 0 ... you get the idea
        (I Hope!). This way we can go from per jet to per object weights.
        :return: An array of weights
        """
        # Get an array of weights from an array of pTs
        if strides is None:
            return self.coeff[np.digitize(jet_pt, self.bin_edges)].astype(np.float32)
        else:
            arr_length = np.sum(strides)  # The total number of objects e.g. Tracks, PFO, etc...
            weights = self.coeff[np.digitize(jet_pt, self.bin_edges)].astype(np.float32)
            weights_ravelled = np.ones(arr_length) * -999  # <-- so that if something is wrong it is obvious
            start_pos = 0
            # Apply the same weighting for each object belonging to the same jet
            for i in range(0, len(strides)):
                weights_ravelled[start_pos: start_pos + strides[i]] = weights[i]
                start_pos = start_pos + strides[i]
            return weights_ravelled


class PreProcTransform:

    def __init__(self, var, min_val=None, max_val=None, apply_log=False, scale=1., take_abs=False):
        self.var = var
        self.min_val = min_val
        self.max_val = max_val
        self.apply_log = apply_log
        self.scale = scale
        self.take_abs = take_abs

    def transform(self, array, dummy_val=-4):
        if self.take_abs:
            array = np.abs(array)
        if self.max_val is not None:
            array = np.where(array > self.max_val, array, dummy_val)
        if self.min_val is not None:
            array = np.where(array < self.min_val, array, dummy_val)
        if self.apply_log:
            array = np.where(array > 0, np.log10(array), dummy_val)
        array *= self.scale
        return array


def create_normalizers(data_generator=None, load=False):

        normalizers = {"TauTrack": preprocessing.Normalization(),
                       "NeutralPFO": preprocessing.Normalization(),
                       "ShotPFO": preprocessing.Normalization(),
                       "ConvTrack": preprocessing.Normalization(),
                       "TauJets": preprocessing.Normalization()}

        if not load:
            assert data_generator is not None
            for batch in data_generator:
                normalizers["TauTrack"].update_state(batch[0][0])
                normalizers["NeutralPFO"].update_state(batch[0][1])
                normalizers["ShotPFO"].update_state(batch[0][2])
                normalizers["ConvTrack"].update_state(batch[0][3])
                normalizers["TauJets"].update_state(batch[0][4])
            for key in normalizers:
                normalizers[key].save_weights(f"data\\{key}_normalizer.h5")
            return normalizers

        normalizers["TauTrack"] = normalizers["TauTrack"]
        normalizers["NeutralPFO"] = normalizers["NeutralPFO"]
        normalizers["ShotPFO"] = normalizers["ShotPFO"]
        normalizers["ConvTrack"] = normalizers["ConvTrack"]
        normalizers["TauJets"] = normalizers["TauJets"]


        return normalizers

def standardise_data(arr, cutoff=1.25):
        """
        Function to standardise the data by removing outliers and if the maximum value in the array is 
        greater than 10 to take the log10 of the data. The outlier removal is done by calculating the 
        interquartile range and setting all data falling outside of the the iqr * cutoff to an upper
        """
        # lower_qtl, upper_qtl = np.percentile(arr, 10), np.percentile(arr, 90)
        # iqr = upper_qtl - lower_qtl
        # cut_off = iqr * cutoff
        # lower, upper =  upper_qtl - cut_off, lower_qtl + cut_off                
        # arr = np.where(arr < upper, arr, upper)
        # arr = np.where(arr > lower, arr, lower)

        if np.max(arr) > 10:
                arr = np.ma.log10(arr)
                arr = arr.filled(-1)
        return arr


limits_dict = {"TauTracks.dEta": PreProcTransform("TauTracks.dEta"),
              "TauTracks.dPhi": PreProcTransform("TauTracks.dPhi"),
              "TauTracks.nInnermostPixelHits": PreProcTransform("TauTracks.nInnermostPixelHits"),
              "TauTracks.nPixelHits": PreProcTransform("TauTracks.nPixelHits"),
              "TauTracks.nSCTHits": PreProcTransform("TauTracks.nSCTHits"),
              "TauTracks.pt": PreProcTransform("TauTracks.pt", max_val=1e7, apply_log=True),
              #"TauTracks.dphiECal": [],
              #"TauTracks.detaECal": [],
              #"TauTracks.jetpt": [],
              "TauTracks.d0TJVA": PreProcTransform("TauTracks.d0TJVA", take_abs=True, apply_log=True),
              "TauTracks.d0SigTJVA": PreProcTransform("TauTracks.d0SigTJVA", take_abs=True, apply_log=True),
              "TauTracks.z0sinthetaTJVA": PreProcTransform("TauTracks.z0sinthetaTJVA", take_abs=True, apply_log=True),
              "TauTracks.z0sinthetaSigTJVA": PreProcTransform("TauTracks.z0sinthetaSigTJVA", take_abs=True, apply_log=True),

              "ConvTrack.dphiECal": PreProcTransform("ConvTrack.dphiECal"),
              "ConvTrack.dphi": PreProcTransform("ConvTrack.dphi"),
              "ConvTrack.detaECal": PreProcTransform("ConvTrack.detaECal"),
              "ConvTrack.deta": PreProcTransform("ConvTrack.deta"),
              "ConvTrack.pt": PreProcTransform("ConvTrack.pt", max_val=1e7, apply_log=True),
              "ConvTrack.jetpt": PreProcTransform("ConvTrack.jetpt", max_val=1e7, apply_log=True),
              "ConvTrack.d0TJVA": PreProcTransform("ConvTrack.d0TJVA", take_abs=True, apply_log=True),
              "ConvTrack.d0SigTJVA": PreProcTransform("ConvTrack.d0SigTJVA", take_abs=True, apply_log=True),
              "ConvTrack.z0sinthetaTJVA": PreProcTransform("ConvTrack.z0sinthetaTJVA", take_abs=True, apply_log=True),
              "ConvTrack.z0sinthetaSigTJVA": PreProcTransform("ConvTrack.z0sinthetaSigTJVA", take_abs=True, apply_log=True),

              "ShotPFO.dphiECal": PreProcTransform("ShotPFO.dphiECal"),
              "ShotPFO.dphi": PreProcTransform("ShotPFO.dphi"),
              "ShotPFO.detaECal": PreProcTransform("ShotPFO.detaECal"),
              "ShotPFO.deta": PreProcTransform("ShotPFO.deta"),
              "ShotPFO.pt": PreProcTransform("ShotPFO.pt", max_val=1e7, apply_log=True),
              "ShotPFO.jetpt": PreProcTransform("ShotPFO.jetpt", max_val=1e7, apply_log=True),

              "NeutralPFO.dphiECal": PreProcTransform("NeutralPFO.dphiECal"),
              "NeutralPFO.dphi": PreProcTransform("NeutralPFO.dphi"),
              "NeutralPFO.detaECal": PreProcTransform("NeutralPFO.detaECal"),
              "NeutralPFO.deta": PreProcTransform("NeutralPFO.deta"),
              "NeutralPFO.pt": PreProcTransform("NeutralPFO.pt", max_val=1e7, apply_log=True),
              "NeutralPFO.jetpt": PreProcTransform("NeutralPFO.jetpt", max_val=1e7, apply_log=True),
              "NeutralPFO.FIRST_ETA": PreProcTransform("NeutralPFO.FIRST_ETA"),
              "NeutralPFO.SECOND_R": PreProcTransform("NeutralPFO.SECOND_R", apply_log=True),
              "NeutralPFO.DELTA_THETA": PreProcTransform("NeutralPFO.DELTA_THETA"),
              "NeutralPFO.CENTER_LAMBDA": PreProcTransform("NeutralPFO.CENTER_LAMBDA", apply_log=True),
              "NeutralPFO.LONGITUDINAL": PreProcTransform("NeutralPFO.LONGITUDINAL"),
              "NeutralPFO.SECOND_ENG_DENS": PreProcTransform("NeutralPFO.SECOND_ENG_DENS", scale=1e5, max_val=10), #  [0, 1e-5]
              "NeutralPFO.ENG_FRAC_CORE": PreProcTransform("NeutralPFO.ENG_FRAC_CORE"),
              "NeutralPFO.NPosECells_EM1": PreProcTransform("NeutralPFO.NPosECells_EM1", apply_log=True),
              "NeutralPFO.NPosECells_EM2": PreProcTransform("NeutralPFO.NPosECells_EM2", apply_log=True),
              "NeutralPFO.energy_EM1": PreProcTransform("NeutralPFO.energy_EM1", apply_log=True),
              "NeutralPFO.energy_EM2": PreProcTransform("NeutralPFO.energy_EM2", apply_log=True),
              "NeutralPFO.EM1CoreFrac": PreProcTransform("NeutralPFO.EM1CoreFrac"),
              "NeutralPFO.firstEtaWRTClusterPosition_EM1": PreProcTransform("NeutralPFO.firstEtaWRTClusterPosition_EM1", scale=1e3, max_val=10),
              "NeutralPFO.firstEtaWRTClusterPosition_EM2": PreProcTransform("NeutralPFO.firstEtaWRTClusterPosition_EM2", scale=1e3, max_val=10),
              "NeutralPFO.secondEtaWRTClusterPosition_EM1": PreProcTransform("NeutralPFO.secondEtaWRTClusterPosition_EM1"),
              "NeutralPFO.secondEtaWRTClusterPosition_EM2": PreProcTransform("NeutralPFO.secondEtaWRTClusterPosition_EM2"),

              "TauJets.centFrac": PreProcTransform("TauJets.centFrac"),
              "TauJets.etOverPtLeadTrk": PreProcTransform("TauJets.etOverPtLeadTrk", take_abs=True, apply_log=True),
              "TauJets.dRmax": PreProcTransform("TauJets.dRmax"),
              "TauJets.SumPtTrkFrac": PreProcTransform("TauJets.SumPtTrkFrac"),
              "TauJets.ptRatioEflowApprox": PreProcTransform("TauJets.ptRatioEflowApprox", take_abs=True, apply_log=True),
              "TauJets.mEflowApprox": PreProcTransform("TauJets.mEflowApprox", max_val=1e7, apply_log=True),
              "TauJets.ptJetSeed": PreProcTransform("TauJets.ptJetSeed", max_val=1e7, apply_log=True),
              "TauJets.etaJetSeed": PreProcTransform("TauJets.etaJetSeed"),
              "TauJets.phiJetSeed": PreProcTransform("TauJets.phiJetSeed"),
            }