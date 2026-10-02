"""Independent diagnostic band-envelope metrics, NOT a validated loudness model.

Dependencies: NumPy only. Gaussian ERB-width analysis filters are an explicitly
approximate diagnostic bank, not ISO roughness or an auditory perception score.
FFT filtering is offline/circular; edge guards are discarded.
"""
from __future__ import annotations
import argparse
import json
import wave
from pathlib import Path
import numpy as np

CENTERS = (65., 130., 260., 520., 1040., 2080., 4160., 8320.)

def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))

def bands(x, fs):
    x = np.asarray(x, dtype=float)
    n = len(x)
    freq = np.fft.fftfreq(n, 1/fs)
    spectrum = np.fft.fft(x)
    hilbert = np.zeros(n)
    hilbert[0] = 1
    hilbert[1:(n+1)//2] = 2
    if n % 2 == 0:
        hilbert[n//2] = 1
    answer = []
    # Discard 150 ms boundaries. At least two seconds recommended.
    guard = int(.15*fs)
    for fc in CENTERS:
        erb = 24.7 * (1 + .00437*fc)
        sigma = erb / 2.355
        transfer = np.exp(-.5*((np.abs(freq)-fc)/sigma)**2)
        analytic = np.fft.ifft(spectrum * transfer * hilbert)
        envelope = np.abs(analytic)[guard:-guard]
        hop = max(1, round(fs/480))
        envelope = envelope[:len(envelope)//hop*hop].reshape(-1, hop).mean(axis=1)
        mean = float(envelope.mean())
        mod_freq = np.fft.rfftfreq(len(envelope), hop/fs)
        mod = np.fft.rfft(envelope - mean)
        powers = np.abs(mod)**2
        weights = np.full(len(mod), 2.)
        weights[0] = 1
        if len(envelope)%2 == 0:
            weights[-1] = 1
        def modulation(lo, hi):
            select = (mod_freq >= lo) & (mod_freq < hi)
            absolute = float(np.sqrt(np.sum(powers[select]*weights[select]))/len(envelope))
            return {"absolute_rms": absolute, "relative_rms": absolute/max(mean, 1e-15)}
        answer.append({"center_hz": fc, "erb_hz": erb, "mean_envelope": mean,
                       "envelope_cv": float(envelope.std())/max(mean, 1e-15),
                       "slow_0p5_30hz": modulation(.5,30),
                       "fast_30_150hz": modulation(30,150)})
    return answer

def summarize(x, fs):
    x = np.asarray(x,dtype=float)
    if len(x) < fs:
        raise ValueError("At least one second required for diagnostic modulation analysis")
    return {"sample_rate": fs, "duration_s": len(x)/fs, "rms": rms(x),
            "peak": float(np.max(np.abs(x))), "dc": float(x.mean()),
            "peak_at_fullscale_count": int(np.count_nonzero(np.abs(x)>=1)),
            "bands": bands(x,fs)}

def read_wav(path):
    with wave.open(str(path),"rb") as wav:
        if wav.getsampwidth()!=2:
            raise ValueError("Expected PCM16 WAV, matching hardware 24-to-16 handoff")
        fs, channels = wav.getframerate(), wav.getnchannels()
        x = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(float)/32768
        if channels!=1:
            raise ValueError("Expected mono reference: no averaging/channel cancellation")
    return x, fs

def compare(paths):
    samples = [read_wav(path) for path in paths]
    if len({(fs,len(x)) for x,fs in samples})!=1:
        raise ValueError("A/B requires identical sample rate and duration")
    target = min(rms(x) for x,_ in samples)
    records = {}
    for path,(x,fs) in zip(paths,samples):
        gain = target/max(rms(x),1e-15)
        records[str(path)] = {"raw": summarize(x,fs), "level_match_gain":gain,
                             "rms_matched":summarize(x*gain,fs)}
    return {"disclaimer":"RMS matching is level control only, not perceptual loudness matching; bands are diagnostic proxies.",
            "target_rms":target, "records":records}

def selftest():
    fs=48000
    t=np.arange(fs*3)/fs
    pure=.1*np.sin(2*np.pi*65.406391*t)
    pair=pure+.1*np.sin(2*np.pi*69.295658*t)
    a,b,c=bands(pair,fs)[0],bands(pair*.125,fs)[0],bands(pure,fs)[0]
    assert a["slow_0p5_30hz"]["relative_rms"]>.2
    assert c["slow_0p5_30hz"]["relative_rms"]<.02
    assert abs(a["slow_0p5_30hz"]["relative_rms"]-b["slow_0p5_30hz"]["relative_rms"])<1e-10
    assert abs(b["slow_0p5_30hz"]["absolute_rms"]/a["slow_0p5_30hz"]["absolute_rms"]-.125)<1e-10
    assert abs(rms(pair*.125)/rms(pair)-.125)<1e-10
    print("PASS independent metrics: beating detection, single-tone control, normalized scale invariance, absolute scale response, RMS control")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--wav",nargs="+",type=Path)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    if args.selftest:
        selftest()
    if args.wav:
        if args.report is None:
            parser.error("--report required")
        destination=args.report.resolve()
        root=Path(__file__).resolve().parent
        if not destination.is_relative_to(root):
            parser.error("Reports restricted to V3 verification")
        destination.write_text(json.dumps(compare(args.wav),indent=2)+"\n",encoding="utf-8")
        print("PASS analyzed",len(args.wav),"WAV files; this is NOT a perceptual acceptance")

if __name__=="__main__":
    main()
