## 기본 라이브러리 Import
import sys
import numpy as npr
import torch
import os
import argparse

## WaveGlow 프로젝트 위치 설정
sys.path.append('/content/drive/MyDrive/새싹_인공지능SW교육/프로젝트/새싹_최종프로젝트/Kss_TTS/tacotron2')
## Tacontron2 프로젝트 위치 설정
sys.path.append('/content/drive/MyDrive/새싹_인공지능SW교육/프로젝트/새싹_최종프로젝트/Kss_TTS/waveglow')

## 프로젝트 라이브러리 Import
from hparams import defaults
from model import Tacotron2
from layers import TacotronSTFT, STFT
from audio_processing import griffin_lim

# from distributed import apply_gradient_allreduce

from tacotron2.train import load_model
from text import text_to_sequence
from scipy.io.wavfile import write
import IPython.display as ipd
import json
import sys
from waveglow.glow import WaveGlow
from denoiser import Denoiser
from tqdm.notebook import tqdm

## dict->object 변환용
class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        
def load_checkpoint(checkpoint_path, model):
    assert os.path.isfile(checkpoint_path)
    checkpoint_dict = torch.load(checkpoint_path, map_location='cpu')
    model_for_loading = checkpoint_dict['model']
    model.load_state_dict(model_for_loading.state_dict())
    return model
        
class Synthesizer:
    def __init__(self, tacotron_check, waveglow_check):
        hparams = Struct(**defaults)
        hparams.n_mel_channels=80
        hparams.sampling_rate = 22050
        
        self.hparams = hparams
        
        model = load_model(hparams)
        model.load_state_dict(torch.load(tacotron_check)['state_dict'])
        model.cuda().eval()#.half()
        
        self.tacotron = model
        
        with open('waveglow/config.json') as f:
            data = f.read()
        config = json.loads(data)
        waveglow_config = config["waveglow_config"]
        
        waveglow = WaveGlow(**waveglow_config)
        waveglow = load_checkpoint(waveglow_check, waveglow)
        waveglow.cuda().eval()
        
        self.denoiser = Denoiser(waveglow)
        self.waveglow = waveglow
        
        
    def inference(self, text):
        assert type(text)==str, "텍스트 하나만 지원합니다."
        sequence = np.array(text_to_sequence(text, ['korean_cleaners']))[None, :]
        sequence = torch.autograd.Variable(torch.from_numpy(sequence)).cuda().long()

        mel_outputs, mel_outputs_postnet, _, alignments = self.tacotron.inference(sequence)
        
        
        with torch.no_grad():
            audio = self.waveglow.infer(mel_outputs_postnet, sigma=0.666)
        audio = audio[0].data.cpu().numpy()
        return audio, self.hparams.sampling_rate
    
    ## \n으로 구성된 여러개의 문장 inference 하는 코드
    def inference_phrase(self, phrase, sep_length=4000):
        texts = phrase.split('\n')
        audios = []
        for text in texts:
            if text == '':
                audios.append(np.array([0]*sep_length))
                continue
            audio, sampling_rate = self.inference(text)
            audios.append(audio)
            audios.append(np.array([0]*sep_length))
        return np.hstack(audios[:-1]), sampling_rate
            
    
    def denoise_inference(self, text, sigma=0.666):
        assert type(text)==str, "텍스트 하나만 지원합니다."
        sequence = np.array(text_to_sequence(text, ['korean_cleaners']))[None, :]
        sequence = torch.autograd.Variable(torch.from_numpy(sequence)).cuda().long()

        mel_outputs, mel_outputs_postnet, _, alignments = self.tacotron.inference(sequence)
               
        with torch.no_grad():
            audio = self.waveglow.infer(mel_outputs_postnet, sigma=0.666)
            
        
        audio_denoised = self.denoiser(audio, strength=0.01)[:, 0].cpu().numpy()
        return audio_denoised.reshape(-1), self.hparams.sampling_rate

## 체크포인트 설정
tacotron2_checkpoint = '/content/drive/MyDrive/새싹_인공지능SW교육/프로젝트/새싹_최종프로젝트/Kss_TTS/tacotron2/output/checkpoint_1450'
waveglow_checkpoint = '/content/drive/MyDrive/새싹_인공지능SW교육/프로젝트/새싹_최종프로젝트/Kss_TTS/waveglow/checkpoints/waveglow_2160'

## 음성 합성 모듈 생성
synthesizer = Synthesizer(tacotron2_checkpoint, waveglow_checkpoint)

## 문장 생성
sample_text = '샘플 음성을 생성할 수 있습니다.'
audio, sampling_rate = synthesizer.inference(sample_text)
## 음성 저장하기
sf.write('문장.wav', audio, sampling_rate)

## 구문 생성
sample_phrase = """
타코트론 모델은 음성 생성 길이가 제한되어 있습니다.
즉 구문을 구성하려면 여러개의 문장을 생성한 후 합쳐야 합니다.
"""
audio, sampling_rate = synthesizer.inference_phrase(sample_phrase)
## 음성 저장하기
sf.write('구문.wav', audio, sampling_rate)