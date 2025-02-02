# SignCLIP - Connecting text and sign language by contrastive learning

This codebase is an adaption of [VideoCLIP](https://github.com/facebookresearch/fairseq/tree/main/examples/MMPT), where general videos (e.g., [HowTo100M](https://www.di.ens.fr/willow/research/howto100m/)) are replaced by specific sign language videos (e.g., [How2Sign](https://how2sign.github.io/)) to bring together text and sign language under a same latent space. See VideoCLIP's original README for an overall introduction to multimodal video understanding and instructions on installing and using the packages.

Video is the most available and rawest representational format that contains human motion and sign language. However, videos are very dense both temporally (*FPS*, frame per second) and spatially (resolution), which are not computationally efficient and thus require a video encoder to extract informative features with reduced dimensionalities for downstream tasks. 

VideoCLIP uses a [S3D](https://github.com/antoine77340/S3D_HowTo100M) model pretrained on the HowTo100M instructional videos as the video encoder and it produces one video token per second. For sign language, it is possible to use a similar video encoder pretrained on sign language videos. A prominent one is the [I3D](https://www.robots.ox.ac.uk/~vgg/research/bslattend/) model pretrained specifically on the sign language recognition task of British Sign Language (BSL).

A potentially more interpretable and universal way of extracting sign language-related features from videos is human pose estimation, for example by [MediaPipe Holistic](https://github.com/google/mediapipe/blob/master/docs/solutions/holistic.md). Recently, quantization-based approaches (such as [SignVQNet](http://nlpcl.kaist.ac.kr/~projects/signvqnet)) have also appeared as an alternative to convert continuous representations of sign language (videos/poses) to discrete tokens similar to spoken language (sub-)words.

Given a 10-second 480p (640×480) RGB (3 channels) video with 30 FPS, we make a rough comparison between the dimensionalities of different video encoders:

| Encoder | Temporal dim. | Spatial dim. | 
|-----------|-----------|-----------|
| Original video | 10x30 | 640×480x3 |
| S3D (pretrained on HowTo100M) | 10 | 512 |
| I3D (pretrained on BSL) | 10 | 1024 |
| MediaPipe Holistic | 10x30 | 543 |
| SignVQNet | 10 | 1024 |

On the text side, we follow VideoCLIP and use the pretrained [BERT](https://huggingface.co/docs/transformers/model_doc/bert) model. One additional [idea](https://github.com/sign-language-processing/transcription/blob/aa2b1ead7d39b2d545b83bac2041b4b539471a7c/pose_to_text/IDEA-CLIP.md) is to use [SignWriting](https://www.signwriting.org/about/what/what02.html#:~:text=SignWriting%20is%20a%20writing%20system,signed%20language%20in%20the%20world.) as a phonetic text representation of sign language.

## FingerCLIP - Fingerspelling Understanding

We start with a simple dataset, [RWTH German Fingerspelling Database](https://www-i6.informatik.rwth-aachen.de/aslr/fingerspelling.php), which contains 35 gestures with video sequences for the signs A to Z and SCH, the German umlauts Ä, Ö, Ü, and for the numbers 1 to 5. Five of the gestures contain inherent motion (J, Z, Ä, Ö, and Ü). We call the model FingerCLIP, a mini version of SignCLIP since fingerspelling is a small and special part of sign language.

The database consists of 1400 videos that contain gestures of 20 different persons. The gestures were recorded by two cameras, one webcam and one camcorder, from two different points of view. The webcam named `cam1` recorded the dominant hands only with a resolution of 320x240 at 25 frames per second, and the camcorder named `cam2` recorded the whole body with a resolution of 352x288 at 25 frames per second. We exclude all `cam1` videos for pose estimation since we assume that the pose estimation model expects whole-body input. Each video file is named `<signer_id>_<letter_id>_<seq_id>_<camera_id>.mpg`. We take all video files and split them randomly into training, dev, and test sets at the ratio of 8:1:1.

### Training

For contrastive training, we use a batch size of 35 and make each batch a collection of 35 different gestures with their corresponding text prompt `'Fingerspell the letter <letter_name> in German Sign Language.'` regardless of the camera type. By optimizing the [InfoNCE loss](https://arxiv.org/abs/1807.03748), we want the video embedding of a gesture to move closer to the corresponding text embedding, as well as to move further away from the remaining 34 negative examples in the same batch. We test the viability of the idea using different combinations of video encoders/features:

- [S3D](https://github.com/antoine77340/S3D_HowTo100M) HowTo100M video features
- [I3D](https://www.robots.ox.ac.uk/~vgg/research/bslattend/data/bsl5k.pth.tar) BSL video features ([code](https://github.com/gulvarol/bsl1k))
    - the original 1024 dimensionality
    - the S3D 512 dimensionality downsampled by average pooling
- Mediapipe pose estimation ([code](https://github.com/J22Melody/pose-pipelines)) 
    - (all poses are 2D normalized and the legs are removed)
    - full body
    - dominant hand only
    - 3D hand normalization
    - 2D pose augmentation (training only)

and training strategies:

- (zero-shot VideoCLIP, no training)
- fine-tune VideoCLIP
- from scratch

The same as the original VideoCLIP model training, in all experiments, the video encoders are frozen and only the weights of the two separate
trainable Transformers (one each for video and text) are updated, initialized with the pre-trained `bert-base-uncased`. We train 25 epochs from scratch and 10 epochs for finetuning, respectively. To start the training, run the following command with the desired config file:

```
python locallaunch.py projects/retri/fingerclip/rwthfs_scratch_pose.yaml --jobtype local_single
```

### Evaluation

We evaluate the models by viewing fingerspelling understanding as a text-video/video-text retrieval task. For both directions, the candidates are ranked by the cosine similarity to the text/video query in the latent space. To run the inference and evaluation on the test set:

```
python locallaunch.py projects/retri/fingerclip/test_rwthfs_scratch_pose.yaml --jobtype local_predict
```

For each test text prompt `'Fingerspell the letter <letter_name> in German Sign Language.'`, there is possibly more than one correct video (e.g, the same letter signed by different signers) in the test video pool, and they are all considered a successful retrieval. We thus evaluate the text-video retrieval task by `precision@k`, i.e., in the k most similar candidates, how many of them are correct answers. For each test video example, there is only one correct text prompt out of the 35 possible prompts. We thus evaluate the video-text retrieval task by `recall@k`, i.e., by taking the k most similar candidates, how much is the chance that one of them is the correct answer. When `k=1`, both `precision@k` and `recall@k` can be interpreted as the retrieval accuracy. For both directions, we add an additional metric `Median R`, which is the median value of the index of the first correct answer in the candidate lists.

Please refer to [results_rwthfs.csv](https://github.com/J22Melody/fairseq/blob/main/examples/MMPT/results_rwthfs.csv) for the evaluation results. Takeaways:

- Neither zero-shot nor fine-tuned VideoCLIP is helpful, just train from scratch.
- I3D features pretrained on BSL works better than S3D features pretrained on HowTo100M.
- Pose estimation as a feature extractor works better than 3D-CNN-based video encoders, probably because it is more universal. It is also more interpretable and operable (for data normalization and augmentation). 
- For fingerspelling, it is beneficial to focus on just the dominant hand.
- Video-text retrieval is more challenging than text-video retrieval. Video-text retrieval is also more valuable since it involves sign language video recognition and understanding, while text-video retrieval can sometimes be easily implemented as a sign language dictionary lookup.
- FingerCLIP solves both directions well, i.e., FingerCLIP understands isolated fingerspelling of the letters in German Sign Language (DGS).

### Demo

To run the inference on an arbitrary test video and text prompts with the best model `rwthfs_scratch_hand_dominant_aug`:

```
python demo_finger.py /data/zifjia/zifan_A.mediapipe.pose
```

We input a pose file that contains the pose estimation of the following video of signing the letter A and various text prompts to compare the similarities:

https://github.com/J22Melody/fairseq/assets/2316987/97c9216e-3072-4f9c-8307-2afcaca47a63

```
('random text', 40.20402145385742)
('Fingerspell the letter Z in German Sign Language.', 59.460140228271484)
('Fingerspell the letter C in German Sign Language.', 65.52384948730469)
('Fingerspell the letter S in German Sign Language.', 52.56050491333008)
('Fingerspell the letter A.', 61.64430618286133)
('Fingerspell the letter a in German Sign Language.', 70.70125579833984)
('Fingerspell the letter A in German Sign Language.', 70.70125579833984)
```

As expected, the model scores the lowest with random text and higher with the designed prompts. It also scores the correct prompt for the letter A the highest, and it scores the same for upper and lower cases since we use `bert-base-uncased` which is case-insensitive.

## SignCLIP v0 - Isolated Sign Language Recognition (ISLR)

We continue our exploration with the [Google - Isolated Sign Language Recognition](https://www.kaggle.com/competitions/asl-signs/data) dataset, which was released for the [Kaggle](https://www.kaggle.com/) competition on classifying isolated American Sign Language (ASL) signs. The dataset contains the pose estimation (by MediaPipe Holistic) of 94,478 signing videos of 250 different individual signs. We split them randomly into training, dev, and test sets at the ratio of 9:0.5:0.5.

### Training

Following the practice in FingerCLIP, we make each batch a collection of unique signs (maximumly 250) with text prompts `'Sign the sign <sign_name> in American Sign Language.'` at training time. We try to implement some of the techniques employed in the [top solutions](https://www.kaggle.com/competitions/asl-signs/leaderboard) of the competition (although most of them use a dedicated classification model instead of a CLIP-like model):

- a selective subset of the keypoints from pose estimation
- a 1D CNN layer before the video Transformer
- aggressive dropout

We always train the models from scratch and inherit the training setup from FingerCLIP. To start the training, run the following command with the desired config file:

```
python locallaunch.py projects/retri/signclip/asl_signs_face.yaml --jobtype local_single
```

### Evaluation

The same evaluation protocol as in FingerCLIP is used, i.e., the ISLR task can be formulated as video-text retrieval, except that now the search space is bigger since the test set's size increases to 4723 and the number of unique text prompts increases to 250. To run the inference and evaluation on the test set:

```
python locallaunch.py projects/retri/signclip/test_asl_signs_face.yaml --jobtype local_predict
```

Please refer to [results_asl_signs.csv](https://github.com/J22Melody/fairseq/blob/main/examples/MMPT/results_asl_signs.csv) for the evaluation results. Takeaways:

- The effectiveness of our approach is proved not only on fingerspelling but also for ISLR.
- Including the face should help understand signs, but only with a selective subset of the keypoints (nose, lips, eyes) because the full set is too dense.
- 1D CNN and aggressive dropout do not further improve the performance.
- Compared to the public leaderboard, there is a margin between video-text retrieval-based classification using SignCLIP and a dedicated classifier trained for the ISLR task.

## SignCLIP v1

To fully realize the power and versatility of SignCLIP, in this version, we do not focus on a single dataset and a single task anymore. Instead, we train the models on more diverse sign language datasets with as large a batch size as we can afford (the original [CLIP](https://openai.com/research/clip) was trained with batch size 32,768). As a reference, VideoCLIP was pretrained on 1.1M videos, and the duration of each is ∼6.5 minutes with ∼110 clip-text pairs.

## Credits

Mathias Müller ([@bricksdont](https://github.com/bricksdont)) proposes the [initial idea](https://docs.google.com/document/d/1mUSLZs_DWc4mHn_nt0soKf1hsTtbrHUUnEX_QBCth5w/edit#heading=h.p699gptqhse9) of a CLIP-like model for sign language.
