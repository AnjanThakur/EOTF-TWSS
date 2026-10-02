# TWSS literature review

Review date: 2026-10-02. This is a focused engineering review, not a systematic or exhaustive survey. No primary-paper collection was present in the original project files inspected. The sources below are publisher articles, author-hosted manuscripts and official dataset documentation. “Not verified” means the available primary source did not support a reliable entry; it is not filled using secondary summaries. Reported paper results are not TWSS results and are not comparable without matching task, acquisition and evaluation.

## Evidence table

The wide table preserves every requested comparison field. For software/method papers without a single experiment, subject/channel fields may legitimately have no single value.

| Paper / primary resource | Year | BCI task | Dataset | Subjects | Channels | Preprocessing | Features | Model | Evaluation | Reported result | Relevance to TWSS |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| [Blankertz et al., Optimizing Spatial Filters for Robust EEG Single-Trial Analysis](https://doc.ml.tu-berlin.de/bbci/publications/BlaTomLemKawMue08.pdf) | 2008 | Hand/foot motor imagery | Berlin BCI examples and methodological review | Multiple examples; no single cohort entry | Described setup: 55 scalp electrodes | Band-pass; spatial filtering | CSP log-power | CSP with LDA | Calibration CV and feedback examples | No single benchmark number extracted | Foundation for supervised CSP and pattern/filter distinction |
| [Ang et al., Filter Bank Common Spatial Pattern Algorithm on BCI Competition IV Datasets 2a and 2b](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2012.00039/full) | 2012 | Four-class MI / two-hand MI | BCI IV 2a / 2b | 9 / 9 | 22 EEG + 3 EOG / 3 EEG | Filter bank; competition causal protocol | CSP features plus mutual-information selection | FBCSP; naive Bayesian Parzen-window classifier; multiclass extensions | Training CV and concealed competition evaluation labels | Mean evaluation kappa 0.569 (2a OVR), 0.600 (2b); not accuracy | Supports separate band/feature-selection benchmark; TWSS uses LDA, so is not an exact reproduction |
| [Barachant et al., Multiclass Brain-Computer Interface Classification by Riemannian Geometry](https://pubmed.ncbi.nlm.nih.gov/22010143/) | 2012 | Multiclass motor imagery | BCI IV IIa | Dataset cohort: 9; detailed exclusions not verified here | Dataset: 22 EEG; analyzed subset not verified here | Exact band/window not verified from accessible authored abstract | SPD covariance matrices; tangent-space vectors | MDRM/MDM; tangent-space LDA with variable selection | Compared against multiclass CSP+LDA; exact split not verified from abstract | Abstract reports reference 65.1%, TSLDA 70.2% mean accuracy | Rationale for experimental covariance/MDM/tangent models; not a prediction of six-channel TWSS performance |
| [Delorme and Makeig, EEGLAB: an open source toolbox for analysis of single-trial EEG dynamics including independent component analysis](https://sccn.ucsd.edu/eeglab/download/eeglab_jnm03.pdf) | 2004 | General EEG analysis | Toolbox with demonstration data | No single evaluation cohort | Supports arbitrary channel count | Filtering, epoch selection, artifact rejection | ICA and time/frequency representations | Analysis toolbox, not one BCI classifier | Method/software demonstrations | No single classifier accuracy asserted | Basis for future artifact assessment; not implemented in frozen preprocessing |
| [Tortora et al., Hybrid Human-Machine Interface for Gait Decoding Through Bayesian Fusion of EEG and EMG Classifiers](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2020.582728/full) | 2020 | Actual walking phase decoding | Recorded treadmill EEG/EMG | 11 healthy subjects | 64 EEG; bilateral three-muscle EMG | Filtering, referencing and artifact handling; rectified/smoothed EMG | Windowed EEG/EMG representations | Separate LSTMs with Bayesian decision fusion | 60/15/25% train/validation/test; simulated EMG degradation | Abstract: >75% hybrid accuracy at 30% EMG amplitude, versus <60% EMG-only | Decision-fusion concept only; task differs, and no such deep model was added |
| [Zhao and Rudzicz, Classifying Phonological Categories in Imagined and Articulated Speech](https://www.cs.toronto.edu/~complingweb/data/karaOne/ZhaoRudzicz15.pdf) | 2015 | Binary phonological categories and mental-state discrimination | Initial multimodal speech corpus | 12 collected, 8 retained; some ICA analysis uses 6 | 64-channel cap; ocular channels treated separately | Ocular separation, 1–50 Hz, channel centering, small Laplacian | Window statistics/derivatives; training-set correlation feature selection | DBN; quadratic/RBF SVM baselines | Leave-one-subject-out | Abstract: >90% consonant categorization; up to 95% state discrimination; not unrestricted word decoding | Different future task, with artifact and modality controls |
| [Chicco and Jurman, The advantages of the Matthews correlation coefficient over F1 score and accuracy in binary classification evaluation](https://link.springer.com/article/10.1186/s12864-019-6413-7) | 2020 | General binary prediction; not a BCI experiment | Synthetic cases and genomics example | Not an EEG cohort | Not applicable | Not EEG processing | Confusion counts | Metric analysis | Synthetic confusion examples and real example | Demonstrates cases where accuracy/F1 hide poor class performance; no EEG accuracy | Supports MCC alongside accuracy, balanced accuracy and class-specific F1 |
| [Schalk et al., EEG Motor Movement/Imagery Dataset, official release](https://physionet.org/content/eegmmidb/1.0.0/) | 2009 | Movement and imagery | EEGMMIDB 1.0.0 | 109 | 64 EEG, 160 Hz | EDF+ release; acquisition task annotations | No prescribed classifier features | No benchmark model prescribed | Dataset protocol, not a leaderboard result | Fourteen runs/subject; no classifier score from release | Exact dataset/task/run provenance for implemented Phase 1 |

## Motor imagery

Motor-imagery communication assigns tasks to commands after supervised calibration. Sensorimotor rhythm changes and spatial contrasts motivate central-region channels; they do not prove a semantic YES or NO representation. Blankertz et al. describe calibration, classifier training and feedback as separate stages, including kinesthetic imagery and spatial filtering. [Author manuscript](https://doc.ml.tu-berlin.de/bbci/publications/BlaTomLemKawMue08.pdf).

**Implemented in our project:** PhysioNet left/right hand imagery trials, within-subject held-out runs and programmed command mapping. **Future research possibility:** feedback and new-session user studies. Dataset labels mean different actions for different runs, so retaining R04/R08/R12 is essential to our interpretation.

## CSP/FBCSP

CSP filters extract projections; patterns express their sensor-space contribution; log-power features drive a classifier. Sparse pattern plots should not be read as anatomical maps. This distinction follows the CSP treatment in the [Blankertz manuscript](https://doc.ml.tu-berlin.de/bbci/publications/BlaTomLemKawMue08.pdf).

Ang et al. report both training CV and hidden-label evaluation; the drop between them illustrates why selection and confirmation differ. Their kappa values are not percentages, and their causal competition constraints differ from whole-run offline filtering. [FBCSP paper](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2012.00039/full).

**Implemented:** frozen CSP4+LDA, separate seeded FBCSP+LDA, fixed band and montage comparisons. **Future:** independent confirmation of any candidate. None of these experiments changes the frozen baseline.

## Riemannian methods

Covariance matrices provide spatial descriptors on the SPD manifold. The authored abstract of Barachant et al. distinguishes nearest Riemannian mean from tangent-space LDA. The full author-hosted PDF was blocked by the host's access protection during this review; detailed split/filter entries are therefore marked unverified rather than reconstructed. [Authored abstract and DOI](https://pubmed.ncbi.nlm.nih.gov/22010143/).

**Implemented experimentally:** Ledoit–Wolf covariance, MDM, tangent-space LDA in Phase 2. TWSS lacks the paper's stated tangent-space variable-selection stage, so its implementation and results must not be presented as a replication. **Future:** robustness/transfer studies using a separate confirmation protocol.

## EEG artifact handling

Delorme and Makeig describe ICA, artifact rejection and visualization as part of general EEG analysis. These tools require careful component and signal interpretation; a toolbox reference does not validate a particular cleaning pipeline. [EEGLAB author manuscript](https://sccn.ucsd.edu/eeglab/download/eeglab_jnm03.pdf).

**Implemented:** finite-sample/channel/window checks and fixed band-pass preprocessing. **Not implemented in Phase 1:** ICA, ASR or explicit ocular/muscle rejection. **Future:** quantify contamination on new recordings and validate cleaning inside training data, without selecting artifact procedures on held-out labels. Six sensors constrain decomposition and anatomical interpretation.

## EEG/EMG fusion

Tortora et al. demonstrate decision fusion in a walking task and evaluate altered EMG reliability. It is a useful design example, not evidence for silent-speech decoding or motor-imagery YES/NO accuracy. [Primary fusion study](https://www.frontiersin.org/journals/neurorobotics/articles/10.3389/fnbot.2020.582728/full).

**Future research possibility:** synchronized EEG/EMG may add a complementary intentional control channel for users with residual muscle function. EMG must be identified as muscle information; performance gains must not be mislabeled as better EEG thought decoding. **Not implemented:** EEG/EMG fusion, synchronized hardware capture, or the paper's neural networks. This task explicitly adds no deep learning.

## Imagined/silent speech

Phonological-category discrimination, rest-versus-active-state classification and full word transcription are different outcomes. Zhao/Rudzicz investigate the first two using multimodal data and subject-held-out evaluation. Their reported high numbers do not establish unrestricted silent speech or a six-channel implementation. [Original ICASSP paper](https://www.cs.toronto.edu/~complingweb/data/karaOne/ZhaoRudzicz15.pdf).

**Future research possibility:** a separate speech-imagery dataset, labels, artifact controls and independent protocol. **Implemented in our project:** speech synthesis of predefined motor-imagery commands; no imagined-speech classifier. The existing feature representation does not prove that a speech decoder can be trained without task-specific evidence.

## KARA ONE

The official release provides fourteen participant archives totaling approximately 24 GB, with EEG, facial and acoustic modalities. This differs from the original paper's analyzed cohort; “14 subjects” should not be retroactively attached to every published result. The website notes that its channel named EMG contains color sensors, so it must not be interpreted as a physiological muscle-fusion recording. [Official KARA ONE release](https://www.cs.toronto.edu/~complingweb/data/karaOne/karaOne.html).

**Planned, not completed:** KARA ONE download/adapter, speech-specific experiments and license review for intended use. The release describes academic/non-profit use and attribution requirements; it is not part of the current downloaded SRM/PhysioNet research results.

## BCI evaluation metrics

MCC uses all four confusion categories; F1 emphasizes the designated positive class. Accuracy alone can conceal asymmetric errors. Chicco/Jurman provide a metric argument, not a BCI performance benchmark. [Primary metric paper](https://link.springer.com/article/10.1186/s12864-019-6413-7).

**Implemented:** accuracy, balanced accuracy, LEFT-positive F1, MCC, confusion counts, acceptance/rejection and command errors. Threshold analysis distinguishes wrong accepted/all attempts from wrong accepted/accepted attempts. UNKNOWN is rejection, not REST. **Future:** confidence calibration, independent threshold confirmation and timed user communication outcomes. Fold SD is not a confidence interval, and useful information transfer cannot be asserted from an untimed replay demo.

## What the evidence supports for TWSS

Classical supervised imagery classification is a reasonable reproducible baseline. The project's own ten-subject results support only the stated within-subject run protocol. The literature motivates alternatives and controls; it supplies no substitute for our own independent validation. Montage, band, comparator and threshold leaders remain exploratory, and separate task results must never be combined into a single claimed end-to-end accuracy.
