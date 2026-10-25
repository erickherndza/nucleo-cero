"""Configuración del motor: dónde están los pesos y en qué dispositivo corre."""
import os
from pathlib import Path

import torch

RAIZ = Path(__file__).resolve().parent.parent
PESOS = os.environ.get('NUCLEO_PESOS', str(RAIZ / 'weights'))


def _elegir_dispositivo():
    """cuda (Colab/servidor) > mps (GPU del Mac M1) > cpu. NUCLEO_DEVICE=cpu fuerza uno."""
    forzado = os.environ.get('NUCLEO_DEVICE')
    if forzado:
        return torch.device(forzado)
    if torch.cuda.is_available():
        return torch.device('cuda')
    if torch.backends.mps.is_available():
        return torch.device('mps')
    return torch.device('cpu')


DEVICE = _elegir_dispositivo()

MODELOS = {
    'RealESRGAN_x4plus.pth': 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
    'GFPGANv1.4.pth': 'https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth',
    'face_detection_yunet_2023mar.onnx': 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
    'face_recognition_sface_2021dec.onnx': 'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx',
}
# CodeFormer: licencia NO comercial (S-Lab 1.0). Solo para pruebas.
MODELO_CODEFORMER = {
    'codeformer.pth': 'https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth',
}
