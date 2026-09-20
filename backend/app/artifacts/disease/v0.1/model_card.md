# Tomato disease model card

- target_crop=tomato
- model_version=tomato-disease-v0.1
- model_status=under_evaluation
- validation_status=under_evaluation
- decision_scope=auxiliary_identification_with_manual_review

MobileNetV3-Small uses ImageNet initialization. PlantVillage is controlled-background foundation data;
IMG-T02 is the real-scene fine-tuning, validation and internal-test source; IMG-T03 is an independent external test.
No Shenxian annotated image was included in this model version. The model supports tomato only, not muskmelon.
Predictions are auxiliary and cannot replace agronomist or plant-pathologist diagnosis.
The system does not provide automatic pesticide dosing or equipment control.
