import sys

import torch
import numpy as np
from pose_format import Pose
from sign_vq.data.normalize import pre_process_mediapipe, normalize_mean_std

from mmpt.models import MMPTModel

import mediapipe as mp
mp_holistic = mp.solutions.holistic
FACEMESH_CONTOURS_POINTS = [str(p) for p in sorted(set([p for p_tup in list(mp_holistic.FACEMESH_CONTOURS) for p in p_tup]))]


sign_languages = [
    'swl',
    'lls',
    'dsl',
    'ise',
    'bfi',
    'gsg',
    'asq',
    'csq',
    'ssp',
    'lsl',
    'rsl',
    'eso',
    'tsm',
    'svk',
    'rsl-by',
    'psr',
    'aed',
    'cse',
    'csl',
    'icl',
    'ukl',
    'bqn',
    'ase',
    'pso',
    'fsl',
    'asf',
    'gss',
    'pks',
    'fse',
    'jsl',
    'gss-cy',
    'rms',
    'bzs',
    'csg',
    'ins',
    'mfs',
    'jos',
    'nzs',
    'ils',
    'csf',
    'ysl',
]

model, tokenizer, aligner = MMPTModel.from_pretrained(
        "projects/retri/signclip_v1/baseline_sp_b768_pre_aug.yaml",
        video_encoder=None,
    )
model.eval()


def pose_normalization_info(pose_header):
    if pose_header.components[0].name == "POSE_LANDMARKS":
        return pose_header.normalization_info(p1=("POSE_LANDMARKS", "RIGHT_SHOULDER"),
                                            p2=("POSE_LANDMARKS", "LEFT_SHOULDER"))

    if pose_header.components[0].name == "BODY_135":
        return pose_header.normalization_info(p1=("BODY_135", "RShoulder"), p2=("BODY_135", "LShoulder"))

    if pose_header.components[0].name == "pose_keypoints_2d":
        return pose_header.normalization_info(p1=("pose_keypoints_2d", "RShoulder"),
                                                p2=("pose_keypoints_2d", "LShoulder"))


def pose_hide_legs(pose):
    if pose.header.components[0].name == "POSE_LANDMARKS":
        point_names = ["KNEE", "ANKLE", "HEEL", "FOOT_INDEX"]
        # pylint: disable=protected-access
        points = [
            pose.header._get_point_index("POSE_LANDMARKS", side + "_" + n)
            for n in point_names
            for side in ["LEFT", "RIGHT"]
        ]
        pose.body.confidence[:, :, points] = 0
        pose.body.data[:, :, points, :] = 0
        return pose
    else:
        raise ValueError("Unknown pose header schema for hiding legs")


def preprocess_pose(pose):
    # pose = pose.normalize(pose_normalization_info(pose.header))
    # pose = pose_hide_legs(pose)
    # pose = pose.get_components(["POSE_LANDMARKS", "FACE_LANDMARKS", "LEFT_HAND_LANDMARKS", "RIGHT_HAND_LANDMARKS"], 
    #                     {"FACE_LANDMARKS": FACEMESH_CONTOURS_POINTS})
    
    pose = pre_process_mediapipe(pose)
    pose = normalize_mean_std(pose)

    feat = np.nan_to_num(pose.body.data)
    feat = feat.reshape(feat.shape[0], -1)

    pose_frames = torch.from_numpy(np.expand_dims(feat, axis=0)).float()

    return pose_frames


def preprocess_text(text):
    caps, cmasks = aligner._build_text_seq(
        tokenizer(text, add_special_tokens=False)["input_ids"],
    )
    caps, cmasks = caps[None, :], cmasks[None, :]  # bsz=1

    return caps, cmasks


def embed_pose(pose):
    caps, cmasks = preprocess_text('')
    poses = pose if type(pose) == list else [pose]
    embeddings = []

    for pose in poses:
        pose_frames = preprocess_pose(pose)

        with torch.no_grad():
            output = model(pose_frames, caps, cmasks, return_score=False)
            embeddings.append(output['pooled_video'].numpy())

    return np.concatenate(embeddings)


def embed_text(text):
    pose_frames = torch.randn(1, 1, 534)
    texts = text if type(text) == list else [text]
    embeddings = []

    for text in texts:
        caps, cmasks = preprocess_text(text)

        with torch.no_grad():
            output = model(pose_frames, caps, cmasks, return_score=False)
            embeddings.append(output['pooled_text'].numpy())

    return np.concatenate(embeddings)


def score_pose_and_text(pose, text):
    pose_frames = preprocess_pose(pose)
    caps, cmasks = preprocess_text(text)

    with torch.no_grad():
        output = model(pose_frames, caps, cmasks, return_score=True)
    
    return text, float(output["score"])  # dot-product


def score_pose_and_text_batch(pose, text):
    pose_embedding = embed_pose(pose)
    text_embedding = embed_text(text)

    scores = np.matmul(pose_embedding, text_embedding.T)
    return scores


def guess_language(pose, languages=sign_languages):
    text_prompt = "And I'm actually going to lock my wrists when I pike."
    text_prompt = "Athens"
    predictions = list(sorted([score_pose_and_text(pose, f'<en> <{lan}> {text_prompt}') for lan in languages], key=lambda t: t[1], reverse=True))
    return predictions


if __name__ == "__main__":
    pose_path = '/shares/volk.cl.uzh/zifjia/RWTH_Fingerspelling/pose/1_1_1_cam2.pose' if len(sys.argv) < 2 else sys.argv[1]

    with open(pose_path, "rb") as f:
        buffer = f.read()
        pose = Pose.read(buffer)

        # print(score_pose_and_text(pose, 'random text'))
        # print(score_pose_and_text(pose, '<en> <ase>'))
        # print(score_pose_and_text(pose, '<en> <gsg>'))
        # print(score_pose_and_text(pose, '<en> <fsl>'))
        # print(score_pose_and_text(pose, '<en> <ise>'))

        # print(guess_language(pose, languages=['fsl', 'gss']))
        # print(guess_language(pose, languages=['ase', 'gsg', 'fsl', 'ise', 'bfi', 'gss']))
        # print(guess_language(pose))

        scores = score_pose_and_text_batch([pose, pose], ['random text', '<en> <ase>'])
        print(scores)