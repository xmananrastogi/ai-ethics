---
marp: true
theme: default
class: invert
style: |
  h1 { color: #38bdf8; font-size: 2.0em; margin-bottom: 0.5em;}
  h2 { color: #38bdf8; font-size: 1.6em; }
  h3 { color: #94a3b8; font-size: 1.2em; font-weight: normal; }
  p, li { color: #cbd5e1; line-height: 1.5; font-size: 1.0em; }
  .highlight-blue { color: #38bdf8; font-weight: 600; }
  .highlight-red { color: #f87171; font-weight: 600; }
  .highlight-green { color: #4ade80; font-weight: 600; }
  blockquote { border-left: 5px solid #38bdf8; padding-left: 20px; color: #fff; font-style: normal; margin-top: 1em; }
---

<!-- paginate: true -->

# AI Ethics Copilot for THOA
### A Proposed Rule-Based AI Screening System for Organ Transplant Documentation

<br>
### **Case Study 1**
Hospital Management (BBMD207L)  
Class: VL2026270100907 | Fall Semester 2026-2027  

**Team:** Manan Rastogi (24bml0004) & Avish Sharma (24bml0025)  
*Presenting to: Dr Sivakumar R*

<!-- 
Speaker Notes:
Good morning Dr. Sivakumar and class. Today we are presenting Case Study 1: an AI Ethics Copilot designed to assist with compliance for the Transplantation of Human Organs Act, or THOA. 
-->

---

# The Context: THOA Compliance

**What is the THOA?**
The Transplantation of Human Organs Act (THOA) was enacted to regulate organ donation and prevent commercial organ trafficking in India.

**The Burden of Proof**
To legally approve a transplant, hospitals must prove the relationship between the donor and recipient is genuine and not financially coerced.
- **Near-Relatives:** Require basic verification (Form 1).
- **Non-Relatives:** Require intense scrutiny, financial affidavits, and police clearance (Form 3, Form 11).

<!--
The THOA is the legal bedrock of our project. It dictates that every transplant must undergo strict verification. The rules change dramatically depending on whether the donor and recipient are related, making the compliance process highly dynamic and complex.
-->

---

# The Problem Statement

**The Compliance Bottleneck**
Every transplant case generates a dossier of 15 to 20 complex legal documents. 

1. **Manual Verification is Slow:** Hospital Authorization Committees spend hours manually reading affidavits and verifying forms.
2. **High Risk of Human Error:** Overlooking a missing Embassy NOC (Form 21) or a mismatched date can result in severe legal penalties for the hospital.
3. **Administrative Delays:** The manual paperwork bottleneck delays urgent, life-saving surgeries.

<!--
The core problem we are solving is administrative bottleneck. When a committee spends all their time checking if a PDF has the right signature, they have less time to evaluate the actual ethics of the case. Furthermore, human error in this process carries massive legal risk.
-->

---

# Literature Review (1/3)

**Domain: Legal Framework & Loopholes**

*Organ Trade in India: A Critical Analysis of the THOTA, 1994* — Merin Mathew (2025)
- **Finding:** Traces the evolution of the legal framework and the massive gaps driving illicit organ trade, noting that manual verification allows loopholes.
- **Relevance:** Proves the critical need for a strict, automated, and unbiased compliance checker that doesn't bend to hospital pressure.

<!--
To ground our proposal, we looked at existing literature. Dr. Sunil Shroff's 2009 paper clearly outlines the exact loopholes our system targets: how forged or incomplete documents slip past human committees. This justifies the need for an automated, objective filter.
-->

---

# Literature Review (2/3)

**Domain: OCR in Healthcare Documentation**

*Deep Learning-Based NLP Data Pipeline for EHR* — JAMIA Open (2023)
- **Finding:** Evaluated OCR and NLP pipelines specifically for scanned medical documents. Found high accuracy, but noted that image preprocessing is the most critical step for success.
- **Relevance:** Validates our architectural choice to use an OpenCV preprocessing pipeline before passing documents to Tesseract OCR and spaCy.

<!--
On the technical side, the 2023 JAMIA Open paper confirms that applying OCR to medical documents is viable, but emphasizes that raw OCR will fail on noisy hospital scans without proper image preprocessing—which informed our pipeline design.
-->

---

# Literature Review (3/3)

**Domain: Human-in-the-Loop Ethics**

*What Are Humans Doing in the Loop?* — American Journal of Bioethics (2024)
- **Finding:** Argues that subjective, contextual judgments in healthcare should never be reduced to an automated "AI score."
- **Relevance:** Directly supports our core design constraint: the AI will objectively verify the *presence* of documents, but the human committee must evaluate the *ethics* (e.g., assessing genuine affection).

<!--
Finally, the ethical literature strongly warns against replacing human judgment. The 2024 AJOB paper validates our decision to make this an "advisory" system that flags missing paperwork, rather than a system that makes the final approval decision.
-->

---

# Proposed Objectives

**What we intend to build:**

1. **Automated Extraction:** Develop a pipeline to extract critical fields (Aadhaar, PAN, Dates, Income) from raw PDF scans.
2. **Rule-Based Screening:** Build a deterministic engine based on THOA sections to automatically flag anomalies.
3. **Explainability Layer:** Ensure every flagged anomaly provides a direct, traceable reference to a specific legal statute.
4. **Advisory Dashboard:** Create a UI for the Authorization Committee that highlights missing data in seconds.

<!--
Based on this research, our objectives are clear: extract the data, run it through deterministic rules, explain why a rule failed, and present it clearly to the committee.
-->

---

# Proposed Methodology: OCR Pipeline

**Converting noisy PDFs into structured data:**

1. **Rasterization:** Convert PDF uploads into high-resolution images (`pdf2image`).
2. **Pre-processing:** Apply Gaussian blur and Otsu thresholding via OpenCV to clean up poor-quality hospital scans.
3. **Text Extraction:** Utilize Tesseract OCR to pull raw text.
4. **Information Retrieval:** 
   - Use **Regular Expressions** to extract structured formats like Aadhaar and PAN.
   - Use **spaCy NLP** to extract Names and Locations from unstructured legal affidavits.

<!--
Our methodology starts with data extraction. We don't just run basic OCR; we use a multi-step pipeline with OpenCV to clean the images first, ensuring we get high-quality text for our NLP models to analyze.
-->

---

# Proposed Methodology: Rule Engine

**Why deterministic rules instead of an LLM?**
Legal compliance requires 100% accuracy, exact traceability, and zero hallucinations. An LLM is not suitable for legal gating.

**The Engine:**
- We will code 16 discrete Python rules mapped directly to THOA laws.
- **Example Rule:** If `relationship == 'NON_RELATIVE'`, system checks if `income_disparity_ratio > 10x`.
- **Outputs:** The engine will output predictable states: `PENDING_REVIEW` (Clean), `ANOMALIES` (Warnings), or `INCOMPLETE` (Missing Docs).

<!--
For the actual decision making, we explicitly chose a deterministic rule engine over an LLM. In legal compliance, hallucinations are unacceptable. We need a system that predictably outputs the exact same flag for the exact same missing document every time.
-->

---

# Proposed System Architecture

**A Modern, Asynchronous Tech Stack**

- **Frontend Interface:** React dashboard for hospital committees.
- **API Gateway:** FastAPI (Python) for strict data validation (Pydantic).
- **Background Processing:** Redis + Celery. 
  - *Why?* OCR is computationally heavy; async processing prevents server timeouts during large uploads.
- **Database:** PostgreSQL for persistent, relational storage of case files.

<!--
Our proposed architecture uses a modern Python stack. The key feature here is the use of Celery and Redis to handle the OCR in the background, ensuring the web interface remains responsive even when uploading a 40-page dossier.
-->

---

# Data Privacy & DPDP Compliance

**Handling sensitive medical and financial data:**

The Digital Personal Data Protection (DPDP) Act imposes strict rules on health data. Our system addresses this by:

1. **Encryption at Rest:** All Personal Identifiable Information (PII) like Aadhaar numbers will be encrypted using **AES-256-GCM** before database insertion.
2. **Data Masking:** Dashboards will automatically mask Aadhaar numbers (e.g., `XXXX-XXXX-1234`) for non-admin users.
3. **Immutable Auditing:** The database will track exactly who viewed or approved a case, ensuring total accountability.

<!--
Because we are handling medical and financial data, privacy is paramount. We are designing the system with DPDP Act compliance from day one, utilizing AES-256 encryption and data masking to protect donor identities.
-->

---

# Expected Challenges

**1. The Handwriting Hurdle**
OCR algorithms struggle significantly with handwritten regional languages (e.g., Hindi, Marathi) which are common in rural Indian affidavits. This requires a robust manual-override fallback.

**2. The Forgery Gap**
Our system can verify that Form 21 *exists* in the PDF. It cannot cryptographically verify if the document is a sophisticated forgery.

**3. Automation Bias**
The psychological risk that a busy Authorization Committee might simply "rubber-stamp" any case the AI marks as clean, ignoring subtle ethical red flags.

<!--
We anticipate three main challenges: OCR failing on bad handwriting, the inability of software to detect physical forgery, and the ethical risk of automation bias, where humans become overly reliant on the machine's verdict.
-->

---

# Evaluation Plan

**How we will measure success:**

1. **Synthetic Dataset:** We will construct a dataset of 100+ simulated transplant cases, including edge cases (e.g., underage donors, missing NOCs).
2. **Metric - OCR Accuracy:** Measure the percentage of correctly extracted critical fields.
3. **Metric - Rule Precision:** Ensure the engine flags 100% of illegal cases with zero false positives.
4. **Final Deliverable:** A working prototype demonstrating the end-to-end flow from PDF upload to an explainable audit report.

<!--
To evaluate our system, we will build a comprehensive synthetic dataset of over 100 cases. Success will be defined by achieving zero false positives in our rule engine and delivering a fully working prototype.
-->

---

# Conclusion

> **"A high-speed compliance filter."**

By automating the tedious, deterministic checks of the THOA documentation process, we aim to eliminate administrative bottlenecks and reduce legal risk.

**The ultimate goal:**
The software evaluates the paperwork, so the human Authorization Committee can dedicate 100% of their time to evaluating the ethics.

<!--
In conclusion, this Copilot is a high-speed compliance filter. It takes the burden of paperwork off the humans, so they can focus on what they do best: ethical evaluation.
-->

---

# Thank You

<span class="highlight-blue" style="font-size: 1.5em;">Questions & Answers</span>

<!--
Thank you for your time. We are happy to take any questions regarding the methodology, the architecture, or the ethical considerations.
-->

---

# Appendix: References (1/5)
**Group 1: THOA & Organ Transplant Law in India**
- *Organ Trade in India: A Critical Analysis of the THOTA, 1994* — Merin Mathew (IJCRT, 2025)
- *From Brain Death to Bureaucratic Delay: A Critical Appraisal of India's Organ Transplant Regime* (LiveLaw, 2026)
- *The Illicit Organ Trade: Biographical, Anatomical, Economic and Legal Aspects* (2025)
- *Organ Transplantation Law in India* (LawBhoomi, 2026)
- *Regulation of Organ Trafficking in India: A Critical Evaluation* (Legal Service India, 2026)
- *Analysis of Kidney and Liver Exchange Transplantation in India (2000–2025)* — Kute et al. (Lancet Regional Health, 2025)

---

# Appendix: References (2/5)
**Group 2: Data Privacy Law**
- *Examining the Significance of the DPDP Act, 2023 in the Context of the Healthcare Industry* (Discover Public Health, 2025)

**Group 3: Explainable AI in Regulatory/Legal Compliance**
- *Ensuring Explainability in AI Systems for Financial Regulatory Compliance* — Santhosh Chitraju (SSRN, 2025)
- *Computational Compliance for AI Regulation: Blueprint for a New Research Domain* (arXiv, 2026)
- *Argumentation-Based Explainability for Legal AI: Comparative and Regulatory Perspectives* (arXiv, 2025)

---

# Appendix: References (3/5)
**Group 4: OCR & Document Information Extraction**
- *Deep Learning-Based NLP Data Pipeline for EHR-Scanned Document Information Extraction* (JAMIA Open, 2022)
- *LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking* (arXiv, 2022)
- *Information Extraction from Unstructured Data Using Augmented Intelligence and Computer Vision* (arXiv, 2023)
- *BERT-Based NER and Relation Extraction for Electronic Medical Records* (Frontiers in Neuroscience, 2023)

---

# Appendix: References (4/5)
**Group 5: Human-in-the-Loop AI & Ethics in High-Stakes Decisions**
- *Human-in-the-Loop Artificial Intelligence in Healthcare: Applications, Outcomes, and Implementation Challenges* (ScienceDirect, 2026)
- *Humans in the Loop, Lives on the Line: AI in High-Risk Decision-Making* (EA Journals, 2025)
- *What Are Humans Doing in the Loop? Co-Reasoning and Practical Judgment...* (American Journal of Bioethics, 2024)

---

# Appendix: References (5/5)
**Group 6: Hybrid Rule-Based + ML Systems for Compliance/Fraud**
- *Advanced Fraud Detection Using Machine Learning Models: Enhancing Financial Transaction Security* (arXiv, 2025)
- *A Survey on Explainable Anomaly Detection* (arXiv, 2022)

**Group 7: Swap/Paired Transplant Matching & Ethics**
- *Adaptation, Comparison and Practical Implementation of Fairness Schemes in Kidney Exchange Programs* (arXiv, 2022)
