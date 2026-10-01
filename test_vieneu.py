from vieneu import Vieneu

tts = Vieneu()   # lần đầu sẽ tải model, hơi lâu

poem = "Nam quốc sơn hà Nam đế cư, tiệt nhiên định phận tại thiên thư."

for name in ("A", "B"):
    audio = tts.infer(poem, ref_audio=f"data/ref/ref_{name}.wav", denoise=True)
    tts.save(audio, f"outputs/clone_{name}.wav")
    print(f"Đã lưu outputs/clone_{name}.wav")

audio = tts.infer(poem, voice="Mai Anh")
tts.save(audio, "outputs/preset.wav")
print("Đã lưu outputs/preset.wav")