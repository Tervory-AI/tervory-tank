# Local index dependencies

This extension is distributed under Apache-2.0; see LICENSE. Retain dependency
LICENSE/NOTICE files when packaging node_modules and the model assets.

- MiniLM ONNX model: Xenova/all-MiniLM-L6-v2, Apache-2.0, revision
  `751bff37182d3f1213fa05d7196b954e230abad9`.
  https://huggingface.co/Xenova/all-MiniLM-L6-v2
  Derived from sentence-transformers/all-MiniLM-L6-v2.
- Transformers.js: Hugging Face, Apache-2.0, 4.3.2.
  https://github.com/huggingface/transformers.js
- Orama: OramaSearch, Apache-2.0, 3.1.18.
  https://github.com/oramasearch/orama
- TypeScript: Microsoft, Apache-2.0, 5.9.3.
  https://github.com/microsoft/TypeScript
- ignore: kael, MIT, 7.0.5.
  https://github.com/kaelzhang/node-ignore
- ONNX Runtime: Microsoft, MIT; transitive versions and integrity digests are
  fixed in package-lock.json. https://github.com/microsoft/onnxruntime

Model preparation only downloads pinned public model artifacts. There is no hosted
embedding endpoint, model account, paid provider or external vector database.
