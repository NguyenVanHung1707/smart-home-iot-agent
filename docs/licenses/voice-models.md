# Voice runtime and model notices

The runtime containers and model weights are downloaded separately and are not
committed to this repository.

| Component | Pinned version/model | License and attribution |
| --- | --- | --- |
| sherpa-onnx | 1.13.4 | Apache-2.0, https://github.com/k2-fsa/sherpa-onnx |
| Vietnamese Zipformer STT | `sherpa-onnx-zipformer-vi-int8-2025-04-20` | Apache-2.0, https://huggingface.co/zzasdf/viet_iter3_pseudo_label |
| Piper | `piper-tts` 1.6.0 | GPL-3.0-or-later, https://github.com/OHF-Voice/piper1-gpl |
| Vietnamese Piper voice | `vi_VN-vais1000-medium` | Dataset VAIS-1000, CC BY 4.0; model card: https://huggingface.co/rhasspy/piper-voices |
| PhoWhisper experiment | `vinai/PhoWhisper-tiny` | Check the upstream model card before downloading or distributing converted weights |

Piper runs as a separate HTTP service. Redistributors of its container must
preserve the GPL notices and provide the corresponding source as required by
GPL-3.0-or-later. The VAIS-1000 voice attribution must accompany demonstrations
or distributions that include the voice model.
