[VIT LOGO — top center]

**VELLORE INSTITUTE OF TECHNOLOGY**

School/Department: SENSE (School of Electronics Engineering)
Course Name & Code: Hospital Management (BBMD207L)
Class: VL2026270100907 | Fall Semester 2026-2027

**Project Title:** AI Ethics Copilot for THOA Compliance: Project Proposal Report

Submitted by: Manan Rastogi, Reg. No: 24bml0004
Submitted to: Dr Sivakumar R

---

[PAGE BREAK]

## Abstract

India's Transplantation of Human Organs Act (THOA) requires Authorization Committees to manually verify fifteen to twenty legal and medical documents per transplant case, a process that is slow, inconsistent, and carries serious legal liability when documents are missed. We propose an AI-assisted compliance screening system that automates the document-reading layer while leaving every legal decision to a human committee. The proposed pipeline uses optical character recognition (OCR) combined with natural language processing (NLP) to extract structured fields from scanned documents, feeds the extracted data through Pydantic-style schema validation to catch malformed input before it reaches any decision logic, and then evaluates the validated data against a deterministic rule engine whose flags are each traceable to a specific THOA provision. This architecture was chosen over a trained machine-learning classifier because legal compliance demands explainability, auditability, and zero hallucination risk in the decision path. This report presents the technical and AI-methodology grounding for that proposal, reviews the relevant engineering literature, and sets out the planned evaluation methodology. It is a proposal; nothing has been implemented or tested.

## 1. Proposed System Architecture

### 1.1 The end-to-end pipeline

Figure 1 presents the proposed system as a sequential pipeline, divided into three functional layers: an AI extraction layer, a deterministic validation and decision layer, and a human review layer. Each stage is designed so that a failure at any point produces an explicit, actionable output rather than a silent error.

[FIGURE: pipeline_tech]

*Figure 1: Proposed end-to-end pipeline showing the AI extraction layer (blue), deterministic decision layer (grey), and human review layer (green). Every step produces a structured output that the next stage can consume or reject.*

The pipeline begins at document upload. A hospital staff member would submit scanned PDFs or images of the case dossier through a web interface. The upload stage validates file type (PDF, JPEG, PNG) and enforces a size limit (10 MB per document), calculating a SHA-256 hash for integrity verification before persisting the file. This is not AI; it is standard input validation, but it sits at the front of the pipeline because malformed uploads are the most common source of downstream failures in document-processing systems.

The extraction layer is where the AI sits. A multimodal large language model, specifically a GPT-4o or Claude-class model, acts as an extraction agent. It receives the raw OCR text from each document and is prompted to produce a structured JSON payload matching a predefined Pydantic schema. The prompt instructs the model to correct obvious OCR artifacts, standardize all dates to ISO 8601 format, and never invent a value that is absent from the source text. For the non-relative affidavit (Form 3), a narrower NLP tool, spaCy or a BERT-based named-entity recognizer, is proposed instead of a generative model, because entity extraction from legal prose does not require generative capability and benefits from the lower hallucination risk of a purpose-built extractor.

The validation layer sits between extraction and decision. Pydantic v2 model validators enforce cross-field THOA rules at the data level: a foreign-national donor without Form 21 raises a validation error; a non-relative case missing Form 3 or Form 11 raises a validation error; a donor under 18 raises a validation error. These checks run deterministically on the structured data, before any rule-engine logic executes. The purpose is to catch malformed or incomplete input early, so that the rule engine never receives data it was not designed to handle. This layered approach, validation before decision, is standard practice in production data pipelines and is proposed here for the same reason: it localises failures to the layer that produced them.

### 1.2 Why rule-based decisions, not a trained classifier

We considered whether a trained machine-learning model could replace the rule engine entirely. A classifier could, in principle, learn to distinguish compliant from non-compliant cases from labelled training data. We rejected this approach for three specific technical reasons.

First, explainability. A classifier that flags a case as "non-compliant" produces a probability score derived from learned weights, not a citation to a legal provision. In a compliance context, the output must be auditable: a reviewer must be able to trace every flag to a specific rule and a specific section of the Act. Deterministic rules provide that traceability by construction; a classifier does not.

Second, training data scarcity and bias. Sufficient labelled transplant-compliance data does not exist in the public domain, and any dataset constructed from hospital records would carry the biases of the institutions that produced it, regional patterns, income skews, and procedural inconsistencies across states. A model trained on such data would learn those biases as signal, producing a system that appears accurate on historical data but performs unpredictably on new cases from institutions with different patterns.

Third, regulatory defensibility. If a hospital or regulator asks why a particular case was flagged, the answer must be reproducible and citable, not "the model scored it 0.73." Deterministic rules, each mapped to a THOA section and stored as external configuration, provide exactly that audit trail.

---

[PAGE BREAK]

## 2. Where AI Is Proposed to Sit (and Where It Isn't)

### 2.1 The extraction layer: multimodal LLM

The largest volume of work in a THOA case is reading. Fifteen to twenty documents must be scanned, parsed, and their key fields extracted: Aadhaar numbers, dates of birth, income declarations, relationship declarations, presence or absence of specific forms. This is the work that is mechanical, voluminous, and error-prone for humans, and it is exactly the work that a multimodal LLM is suited to perform.

We propose using a GPT-4o or Claude-class model as an extraction agent, prompted to act as a strict data parser. The model receives raw OCR text and produces a JSON payload conforming to the TransplantCase Pydantic schema. The prompt includes explicit directives: never invent missing values, correct only obvious OCR artifacts, standardize dates, and output raw JSON with no commentary. This approach demonstrates the responsible use of a generative model: it is applied to the task where it adds value (reading unstructured text) and is excluded from the task where it would introduce risk (making legal decisions).

### 2.2 The affidavit layer: narrow NER, not generative AI

For the non-relative affidavit (Form 3), the system proposes a different tool. This document contains narrative statements about the relationship between donor and recipient, and the extraction task is to pull named entities (persons, dates, locations, organizations), stated relationship duration, and key events mentioned in the text. This is a named-entity recognition (NER) task, and it is better served by a purpose-built NER model, spaCy or a BERT-based fine-tuned extractor, than by a generative LLM. The narrower model produces labelled spans with confidence scores rather than free text that may include fabricated details, making it the safer choice for documents presented to an Authorization Committee as factual context.

### 2.3 The decision layer: zero LLM involvement

The compliance decision itself, the output that tells the committee which rules were triggered and why, is proposed to contain no LLM calls at all. The rule engine is a Python class that evaluates a validated TransplantCase against a set of deterministic if-then checks, each stored as external JSON configuration. Each check maps to a THOA section: Section 9(1B) for donor age, Form 21 for foreign nationals, Section 9(3) and Forms 3 and 11 for non-relatives. The output is a list of rule results, each containing the rule code, severity, message, legal reference, and a flag indicating whether the legal reference has been verified by a qualified professional. There is no confidence score, no probability, no neural network. The same input produces the same output, deterministically, every time. Figure 2 illustrates where AI is proposed to sit and where it deliberately does not.

[FIGURE: ai_boundary]

*Figure 2: Proposed responsibility split across the three system layers. AI handles extraction only; the decision path is fully deterministic and terminates in human review.*

## 3. Technical Literature Review

### 3.1 Theme One: explainability in compliance-adjacent AI

The question of how to make automated compliance decisions legible to human auditors is not new, but it has gained urgency as regulatory bodies in both finance and healthcare begin to scrutinise AI-assisted decision-making. Chitraju's analysis of explainability in financial regulatory compliance frames the core problem: when an automated system flags a transaction or a case, the flag must be interpretable by the human who must act on it, and that interpretability must survive audit, not just initial review. Chitraju argues that post-hoc explanation techniques, which attempt to explain a model's output after the fact, are structurally weaker than designs where the decision logic is inherently transparent. This directly informs our proposed architecture: a deterministic rule engine is transparent by construction, because each output is traceable to a named rule and a named legal provision, whereas a trained classifier would require additional explanation layers that introduce their own failure modes.

The arXiv paper on computational compliance for AI regulation extends this argument to a systems level. It proposes "computational compliance" as a research domain concerned with building systems whose behaviour can be formally verified against regulatory text. The paper's central observation is that compliance is not a property of a model's output; it is a property of the system's design, and it must be provable, not merely probable. For our proposed pipeline, this means the rule engine's compliance with THOA must be verifiable by inspection of the rule definitions and their mapping to statutory sections, not by testing a classifier on historical data and hoping the accuracy metric captures compliance.

The arXiv paper on argumentation-based explainability for legal AI contributes a comparative taxonomy of explanation methods: rule-based, example-based, and argumentation-based. It finds that rule-based explanations, where each decision is presented as a chain of logically connected premises, are the most effective for legal reasoning contexts because they mirror the structure of legal argument itself. This is exactly the explanation model our proposed rule engine adopts: each flag cites a rule, the rule cites a THOA section, and the evidence from the case data that triggered the rule is presented alongside the citation. The committee receives not a verdict but a structured argument it can interrogate.

### 3.2 Theme Two: document understanding and information extraction

The technical challenge at the front of the pipeline is extracting structured data from messy, scanned documents. Hsu and colleagues' evaluation of deep-learning NLP pipelines for electronic health record extraction provides the most directly relevant empirical grounding. They tested OCR-plus-NLP pipelines on scanned medical documents and found that image preprocessing, deskewing, denoising, and thresholding, was the single most critical factor in downstream extraction accuracy. Raw OCR on unprocessed scans produced unacceptable error rates; the same OCR applied to preprocessed images achieved dramatically better field-level accuracy. This finding informed our proposed pipeline design: an OpenCV preprocessing stage (deskew, denoise, Otsu thresholding) is planned before any text extraction occurs, because the quality of the extraction depends on the quality of the input image, not just the quality of the OCR engine.

Huang and colleagues' LayoutLMv3 paper represents the current frontier of layout-aware document understanding. The model jointly processes text, layout, and image features during pre-training, allowing it to understand not just what text a document contains but where that text sits on the page relative to headers, tables, and form fields. For a future version of the system that moves beyond regex and NER-based extraction toward true form-field understanding, LayoutLMv3 is the most promising candidate architecture. At the proposal stage, however, we intend to start with a simpler pipeline (Tesseract OCR plus regex and spaCy NER) because it is faster to prototype, easier to debug, and sufficient for the structured forms that dominate THOA documentation. LayoutLMv3 is the planned upgrade path, not the starting point.

The arXiv paper on information extraction from unstructured data using augmented intelligence and computer vision complements this by addressing tabular data extraction from scanned documents. THOA case files contain not just narrative affidavits but also tabular forms, and extracting data from tables requires detecting cell boundaries and row-column relationships, a task that pure OCR handles poorly. The paper's approach, combining OCR with deep-learning object detection for table structure recognition, is the technique we would adopt if the system encounters heavily tabular documents that the simpler regex-based pipeline cannot parse.

The Frontiers in Neuroscience paper on BERT-based NER and relation extraction for electronic medical records provides the technical foundation for the affidavit extraction module. The authors demonstrate that a BERT-based model fine-tuned on medical text can perform joint entity recognition and relation extraction, identifying both the entities (patients, dates, conditions) and the relationships between them (patient-diagnosedWith-condition). For the Form 3 affidavit, this approach would extract not just named entities but the relational structure of the narrative: who is related to whom, for how long, and what events are cited as evidence. This is the planned extraction method for the affidavit module, and it is the reason we propose spaCy or a BERT-based NER model rather than a generative LLM for this specific task.

### 3.3 Theme Three: hybrid rule and anomaly detection patterns

The final theme bridges the gap between rule-based systems and machine learning in compliance and fraud detection. The arXiv paper on advanced fraud detection using machine learning models surveys the landscape of hybrid approaches in financial transaction monitoring. It contrasts pure rule-based heuristics (fixed thresholds, velocity rules, blacklists) with supervised and unsupervised ML, and finds that the most effective production systems combine both: rules handle the known, deterministic patterns, while ML handles the novel, emerging patterns that rules cannot anticipate. For our proposed system, this hybrid pattern is relevant but deliberately restricted: we propose rules for the known THOA requirements and flagging for anomaly patterns (such as income disparity), but we do not propose training an ML model on transplant data because the data does not exist in sufficient quantity or quality. The hybrid pattern informs the design, even if the ML component remains aspirational.

The arXiv survey on explainable anomaly detection provides a taxonomy of techniques for making anomaly scores interpretable, including reconstruction-based methods, proximity-based methods, and rule-based methods. The paper's central finding, that rule-based anomaly explanations are more actionable for human reviewers than score-based explanations, reinforces our decision to present flags as rule citations rather than anomaly scores. When the income-disparity check triggers a warning, the committee receives the rule, the threshold, the actual income figures, and the THOA section, not a probability that the case is anomalous.

The arXiv paper on fairness schemes in kidney exchange programmes provides the most domain-specific technical grounding in this review. The authors compare multiple fairness criteria for kidney exchange matching algorithms and find that the choice of fairness definition materially changes which patients receive transplants, a result that generalises to our proposed system: any threshold we choose for income disparity or relationship duration is a value judgment encoded as a parameter, and different parameter values would produce different flag patterns. This is the technical reason the paper's authors argue for transparency in threshold selection, and it is the reason our proposed system stores thresholds as external configuration with explicit legal-verification flags, so that a domain expert can adjust them without modifying application code. Figure 3 summarises the proposed OCR extraction pipeline that feeds data into this threshold logic.

[FIGURE: ocr_detail]

*Figure 3: Proposed OCR extraction pipeline from raw upload through preprocessing, text extraction, field parsing, and schema validation.*

---

[PAGE BREAK]

## 4. Proposed Evaluation Plan

Since real transplant records are sensitive medical and legal data, the team proposes to evaluate the system entirely on synthetic test cases. The evaluation plan has two independent dimensions: OCR extraction accuracy and rule-engine correctness, measured separately so that failures in one layer can be attributed to that layer rather than propagated.

### 4.1 Synthetic test data

The team proposes constructing a dataset of 100 or more simulated transplant cases, each conforming to the TransplantCase Pydantic schema. The dataset will include: clean-pass cases (sibling donation, all documents present), non-relative cases (friend donation, full documentation, routed to committee review regardless), critical-fail cases (17-year-old donor, missing Form 21 for foreign national), red-flag cases (non-relative with high income disparity, missing financial affidavit), and edge cases (cross-state donor requiring Form 20, swap transplant). Each case will be labelled with the expected rule-engine outcome, providing a ground-truth reference against which the system's output can be compared.

### 4.2 Extraction accuracy metric

OCR field-extraction accuracy will be measured as the percentage of critical fields (Aadhaar number, date of birth, income, relationship type) correctly extracted from synthetic scanned documents. This metric will be computed per document type and per field, so that weaknesses in the pipeline (for example, poor extraction of handwritten income figures from affidavits) can be identified and addressed independently of the rule engine. A target of 95 per cent field-level accuracy on clean scans and 80 per cent on degraded scans is proposed as the minimum viable threshold.

### 4.3 Rule-engine correctness metric

Rule-engine correctness will be measured against the labelled synthetic dataset. The primary metric is that 100 per cent of illegal cases (minor donor, missing required forms, foreign national without Form 21) are flagged, and zero false-positive "reject" flags are produced on clean compliant cases. The team proposes to report this as a binary pass/fail per rule, not as a single aggregate score, because a rule engine that passes 15 out of 16 rules is not acceptable in a compliance context; every rule must pass.

---

[PAGE BREAK]

## 5. Anticipated Technical Challenges and Limitations

### 5.1 OCR accuracy on degraded documents

The single largest technical risk in the proposed pipeline is OCR accuracy on poor-quality scans and handwritten regional-language documents. Tesseract OCR performs well on clean, printed English text but degrades sharply on noisy scans, handwritten text, and non-Latin scripts. Indian affidavits are frequently handwritten in Hindi, Marathi, or other regional languages, and the proposed pipeline cannot guarantee reliable extraction from such documents. The planned mitigation is to flag low-confidence extractions (below 80 per cent OCR confidence) for human review rather than to guess, but this means the system's reliability is directly correlated with document quality, and that correlation is an inherent limitation, not a bug to be fixed.

### 5.2 Document forgery is out of scope

The proposed system verifies that a document exists, that its contents are internally consistent, and that it conforms to the expected schema. It does not, and cannot, detect a sophisticated forgery. A fabricated Form 21 that matches the expected format and contains plausible data will pass every check the system performs. This is a fundamental limitation of content-based screening, and it means the system is a documentation-completeness tool, not a document-authenticity tool. The committee's role in verifying document provenance remains essential.

### 5.3 Heuristic thresholds require expert calibration

Several rule-engine checks rely on numeric thresholds that are not specified in the Act. The income-disparity flag, for example, triggers when the recipient's income exceeds the donor's by a configurable ratio. That ratio is a heuristic drawn from fraud-detection literature, not a legal standard. In a real deployment, any such threshold would need to be calibrated by a legal or domain expert who understands the specific distribution of income patterns in transplant cases. The team proposes to expose these thresholds as external configuration parameters with a "needs legal verification" flag, so that they can be adjusted without modifying application code, but the initial values are student-chosen heuristics and should be treated as such.

### 5.4 Automation bias

The psychological tendency for human reviewers to defer to automated outputs, automation bias, is well documented in the human-in-the-loop literature. If the system consistently flags cases as clean, a busy committee may begin to treat those flags as endorsements rather than as inputs to their own judgment. The proposed mitigation is a dashboard design that presents flags with their legal citations and recommended next steps rather than a single verdict, but this is a design-level mitigation, not a guarantee, and it requires ongoing attention during deployment.

---

[PAGE BREAK]

## 6. Security and Deployment Considerations

Because the system will process Aadhaar numbers, PAN numbers, income declarations, and medical records, it must be designed with data protection as a foundational requirement, not a retrofit.

**Encryption.** Data will be encrypted at rest using AES-256-GCM for all identity fields (Aadhaar, PAN) before database insertion. API traffic will be encrypted in transit using TLS 1.3. The design follows the standard principle of defence in depth: application-layer encryption for the most sensitive fields, transport-layer encryption for all network traffic.

**Access control.** The system proposes role-based access control with three tiers: administrators (full access), reviewers (access to assigned cases only), and viewers (read-only access to de-identified data). Reviewers will see only the cases assigned to them, enforcing the principle of least privilege by design rather than by convention.

**Audit logging.** Every action on the system, upload, screening, override, decision, report generation, will be logged with actor, timestamp, action type, and case identifier in an append-only log. The audit log is immutable by design: records can be appended but never edited or deleted. This provides the accountability trail required by the DPDP Act and by good engineering practice.

**Data masking.** Aadhaar and PAN numbers will be masked to the last four digits in all non-administrative views, including committee-facing dashboards and generated PDF reports. Full values will be decrypted only when a specific workflow requires them, and the decryption event itself will be logged.

**Deployment.** The proposed deployment architecture uses Docker Compose for the backend (FastAPI, PostgreSQL, Redis, Celery worker), a separate container for the React frontend, and nginx for reverse proxying with TLS termination. Async processing via Celery and Redis ensures that computationally heavy OCR operations do not block the API server, maintaining responsive upload and query performance for the committee dashboard.

---

[PAGE BREAK]

## 7. Inference: What This Research Taught Us

The most consistent pattern across the ten papers reviewed is this: in compliance-adjacent systems, explainable and rule-based methods keep appearing alongside machine learning, not instead of it. The financial compliance literature (Chitraju, Computational Compliance) shows that regulators demand traceability that ML alone cannot provide. The document understanding literature (Hsu, LayoutLMv3, BERT NER) shows that the extraction layer benefits enormously from deep learning, but the downstream decision layer benefits from determinism. The fraud detection literature (Advanced Fraud Detection, Explainable Anomaly) shows that hybrid architectures, rules for known patterns, ML for emerging ones, are the production standard, but that the rule component carries the compliance weight. Reading these together, the pattern is not "ML is better than rules" or "rules are better than ML." It is that different layers of a compliance system have different explainability requirements, and the architecture must match the requirement of each layer, not impose a single paradigm everywhere.

This research shaped one specific architectural decision in the proposed pipeline more than any other: placing Pydantic schema validation between the extraction layer and the rule engine. The original concept was extraction feeds directly into rules. The literature on data quality in document-processing pipelines (Hsu et al.) and on computational compliance (arXiv 2026) made clear that the boundary between "data that is well-formed enough to evaluate" and "data that is not" must be explicit, auditable, and separated from the decision logic. Pydantic validators provide that boundary: they catch malformed input at the data layer, before the rule engine ever sees it, and they produce structured error messages that the audit log can record. This is a small architectural choice, but it is the one that most directly determines whether the system's failures are diagnosable or mysterious.

The technical limitation I would want stress-tested before this system could move past proposal stage is OCR robustness on real Indian document scans. The literature (Hsu et al.) shows high accuracy on clean EHR scans; Indian THOA documents, handwritten in regional languages on poor-quality paper, are a materially different input distribution. Until the extraction layer's accuracy is measured on a representative sample of such documents, the entire pipeline's reliability is an assumption, and assumptions about OCR accuracy on degraded input are the single most common source of failure in production document-processing systems. That is the test I would run first.
