[VIT LOGO — top center]

**VELLORE INSTITUTE OF TECHNOLOGY**

School/Department: SENSE (School of Electronics Engineering)
Course Name & Code: Hospital Management (BBMD207L)
Class: VL2026270100907 | Fall Semester 2026-2027

**Project Title:** AI Ethics Copilot for THOA Compliance: Project Proposal Report

Submitted by: Avish Sharma, Reg. No: 24bml0025
Submitted to: Dr Sivakumar R

---

[PAGE BREAK]

## Abstract

The Transplantation of Human Organs Act (THOA), 1994, as amended in 2011, requires hospitals and their Authorization Committees to establish that every living-donor transplant is genuine and free of commercial dealing. In practice this means a committee of doctors and administrators manually reading a dossier of fifteen to twenty legal and medical documents, under pressure, with serious legal penalties on the line. We propose an AI-assisted compliance screening system, a copilot that reads and structures these documents for the committee rather than deciding for it. The proposed pipeline combines a multimodal large language model for document extraction, classical NLP for affidavit fact extraction, and a deterministic, fully explainable rule engine that flags documentation anomalies against specific provisions of the Act. The central design principle of this proposal is that artificial intelligence handles the mechanical work of reading, while every legal decision remains with the human Authorization Committee. This report presents the legal, ethical, and regulatory foundation of that proposal, and sets out the safeguards we plan to build into the system before it could ever be considered for real deployment. It is, at this stage, a proposal; nothing has been implemented or tested.

---

[PAGE BREAK]

## 1. Introduction: What THOA Actually Requires

### 1.1 The two tracks of living donation

India's organ transplant law rests on a distinction that runs through the entire regulatory architecture. Section 2(i) of the Act defines a closed list of "near relatives": spouse, son, daughter, father, mother, brother, sister, grandfather, grandmother, grandson, and granddaughter. A transplant between near relatives is treated as presumptively benign; it requires comparatively light documentation, principally a certificate in Form 1, or Form 2 in the case of a spouse, establishing the relationship.

Everyone outside that list falls into the second track. A non-relative donor, a friend, a distant cousin, a neighbour, an employer's employee, must satisfy a far heavier burden of proof. Under Section 9(3), the Authorization Committee must satisfy itself that the donation is motivated by "affection or attachment" towards the recipient and not by any monetary consideration. That subjective finding is supported by a stack of documents: the donor's consent in Form 3, a financial affidavit from both parties swearing no commercial dealing, a police verification report, and in the case of foreign nationals, a relationship certificate in Form 21. A single case file can run to fifteen or twenty documents.

### 1.2 The proposed classification logic

Figure 1 maps the two-track structure of the Act as we intend to encode it in the proposed rule engine. The point of the figure is that every branch terminates either in routine documentation or in a mandatory human decision; our proposed system is designed to enforce exactly this branching, mechanically and consistently.

[FIGURE: thoa_flow]

*Figure 1: Proposed classification of living-donor cases under THOA, mapped to the planned rule branches (REL-01 to REL-05).*

### 1.3 The Act's intent

The drafters' intent is not hard to read. Sections 18, 19 and 19A of the Act criminalise unauthorized removal of organs and commercial dealing in them, with penalties that were substantially stiffened in the 2011 Amendment. The verification apparatus of forms, affidavits and committee hearings is the enforcement mechanism for those prohibitions. The law does not want the transplant itself; it wants the donor-recipient relationship to be true, and it has chosen paperwork as its instrument of truth-telling. That choice is the foundation on which our proposal is built, and, as the literature reviewed in this report shows, it is also the foundation's fault line.

---

[PAGE BREAK]

## 2. The Problem: Manual Review Under Pressure

### 2.1 Why the manual process fails

The burden of verifying this documentation falls entirely on human Authorization Committees. Each case is reviewed by hand: forms checked for presence, dates cross-checked against birth certificates, income figures compared across affidavits, embassy certificates confirmed for foreign donors. The process is slow, and it is inconsistent. One reviewer may catch a missing Form 21 for a foreign donor; another, working under time pressure on a Friday evening, may not. The literature on human error in high-stakes document review is unambiguous on this point: accuracy decays under workload and time pressure, and the decay is not evenly distributed across reviewers.

### 2.2 The legal timeline

This inconsistency now sits inside a judicial deadline. In January 2024, the Delhi High Court ruled that living-donor transplant cases must be decided within a window of six to eight weeks. The intention is plainly to protect patients, for whom delay can be a matter of clinical deterioration, but the effect is to compress the very process that produces the paperwork bottleneck. A committee cannot simply take longer; it must decide faster while the stakes remain exactly as high.

### 2.3 Liability for the hospital

The consequences of a missed document fall on the hospital and its committee members. Section 9(3A) and the 2011 Amendment place continuing obligations on hospitals that perform transplants; a transplant that proceeds without the required verification exposes the institution to penalties under Sections 18 and 19, and exposes the committee to questions it will struggle to answer. We propose a system that does not remove this responsibility, because the law deliberately leaves it with the committee, but that reduces the probability of mechanical error. The scope of our proposal is a screening and flagging tool for the Authorization Committee. It will not approve, reject, or opine on the merits of any case. It will only verify that the required documentation is present, internally consistent, and traceable to the specific provisions of the Act that require it.

---

[PAGE BREAK]

## 3. Why This Is an AI Ethics Project

### 3.1 The proposed division of labour

The design of this system is, at its core, an ethical argument about where machine intelligence is appropriate. We propose to use AI for exactly one job: converting messy, scanned, unstructured documents into clean structured data, work that is mechanical, voluminous, and error-prone for humans. For that task we plan to use a multimodal large language model (a GPT-4o or Claude-class model) as an extraction agent, prompted to act as a strict parser: correcting obvious OCR artifacts, standardizing dates, and never inventing a value that is not present in the source text. For the affidavit in non-relative cases, we intend to use a narrower NLP tool, spaCy or a BERT-based named-entity recognizer, which pulls named entities and facts from legal prose with less hallucination risk than a generative model.

### 3.2 The decision layer stays deterministic

The compliance decision itself will deliberately contain no LLM at all. The proposed rule engine is a set of deterministic, if-then checks in Python, each mapped to a specific provision of the Act: Section 9(1B) for donor age, Form 21 for foreign nationals, Section 9(3) and Forms 3 and 11 for non-relatives, and so on. Every flag the engine produces will cite the rule and the section that triggered it. There is no score, no confidence interval, no probability. The same input produces the same output, forever. Figure 2 shows the proposed end-to-end pipeline and the boundary the ethics argument depends on: no generative model sits on the decision path, and the pipeline terminates in a human committee action, never an automated verdict.

[FIGURE: pipeline]

*Figure 2: Proposed system pipeline. AI performs extraction only; the decision path is deterministic and terminates in the human committee.*

### 3.3 Why a black-box classifier would be unacceptable here

The obvious alternative, a trained machine-learning model that classifies cases as compliant or non-compliant, is the wrong tool, for three reasons. First, explainability: a model that flags a case cannot say why in terms a lawyer can audit. Under Section 9, a committee that acts on a flag must be able to justify its decision; a citation to a model's hidden weights is not a justification. Second, learned bias: a model trained on historical transplant data would inherit whatever biases that data contains, regional, income-based, or linguistic, silently, in a way a written rule cannot. Third, legal defensibility: if a hospital is ever asked why a case was flagged, the answer must be reproducible and citable; deterministic rules provide that, a classifier does not. This is not a technical preference but an ethical position, and the reason this is an AI ethics project rather than simply an AI project.

---

[PAGE BREAK]

## 4. Legal and Ethical Literature Review

### 4.1 Theme One: gaps in THOA enforcement

Mathew's critical analysis of the 1994 Act traces the evolution of the legal framework and argues that the enforcement architecture has historically been reactive, driven by scandal and amendment rather than by design. Her comparative reading against the United States and Australia shows that India's form-heavy verification regime is, on paper, among the strictest in the world, and that the gap lies not in the letter of the law but in its application. That conclusion is directly relevant to our proposal: a rule engine that mechanically enforces the letter of the Act does not add new law; it makes existing law enforceable in practice, which is precisely the gap Mathew identifies.

A similar critique emerges from the Legal Service India evaluation of organ trafficking regulation, which carefully separates three concepts the public discourse routinely conflates: organ trafficking, organ trade, and transplant tourism. Each has a different legal shape under Indian law, and the distinction matters for a screening system because the documentary signals of each are different. Our proposed engine's anti-commercialization rules, the financial affidavit check, the police verification requirement, the income-disparity flag, map onto this taxonomy. The Zenodo study of the illicit organ trade reinforces the point through case studies: commercial arrangements are routinely laundered through the non-relative route, precisely because that route carries the heaviest documentary burden and the heaviest verification load on committees. A system that helps committees carry that load is therefore not merely an administrative convenience; it is an enforcement tool.

The LiveLaw appraisal of India's transplant regime adds a process-level finding. It examines how the screening committee's workload differs between near-relative, non-near-relative, and foreign-national cases, and observes that the bureaucratic apparatus built to prevent trafficking has become a delay-generating machine in its own right. This is the tension at the heart of our proposal: the same forms that protect against commercial dealing also delay genuine transplants. Our planned system is an attempt to resolve that tension in one direction, by making the verification process faster without making it looser.

### 4.2 Theme Two: the process under real-world data

LawBhoomi's explainer of organ transplantation law walks through the advisory committee structure under Section 13A, the commercial-dealing penalties under Sections 19 and 19A, and the rule-making authority under Section 24, and it is the source of the January 2024 Delhi High Court timeline that anchors our problem statement. What the explainer makes clear is that the Act contemplates committees that are deliberative bodies, not clerical ones. When the system's documentation checks are handled by software, the committee's actual statutory function, weighing affection and attachment, hearing the parties, exercising judgment, is what remains. Our proposal is designed around exactly that remainder.

Kute and colleagues' multicentre retrospective cohort study of kidney and liver exchange transplantation in India, drawing on 65 centres over twenty-five years, is the strongest empirical grounding in this review. It demonstrates that exchange and non-relative transplants, the very cases that carry the heaviest verification burden, are a substantial and growing share of Indian practice, and that they function within the Authorization Committee framework at scale. Reading it together with LiveLaw, one conclusion is unavoidable: the volume of such cases will keep rising, and a manual-only verification process will not scale with it. This is the empirical case for automation, and it is also a caution, since the study's findings on how outcomes vary across centres suggest that consistency, not just speed, is the problem to be solved.

---

[PAGE BREAK]

## 4. Legal and Ethical Literature Review (continued)

### 4.3 Theme Three: the limits of automating subjective judgment

The American Journal of Bioethics paper, "What Are Humans Doing in the Loop?", makes the argument that our entire design rests on: subjective, contextual judgments should not be reduced to a score. The authors examine how clinicians actually use machine-learning decision aids, and find that the value of the human in the loop lies in co-reasoning with the machine, applying practical judgment to the machine's output rather than deferring to it. For our project this is a design specification, not a philosophical nicety. The "affection and attachment" standard of Section 9(3) is a judgment about the truth of a human relationship. We propose that the system extract facts, stated relationship duration, named shared events, entities mentioned in the affidavit, and present them to the committee, and that it never compute an "affection score." If it did, the system could be gamed by writing emotionally persuasive affidavits, and the legal safeguard of Section 9(3) would be silently replaced by a proxy. That is the precise failure the AJOB authors warn against.

The ScienceDirect review of human-in-the-loop AI in healthcare surveys the implementation and regulatory dimensions of such systems, including the liability question: when AI assists and a human decides, where does responsibility lie when the outcome is wrong? The review's answer, which we adopt as policy, is that the human decision-maker retains responsibility, and that the system must therefore be engineered to support, not pressure, the human. That is why our proposed dashboard presents flags with their legal references and recommended next steps, and never a verdict. The EA Journals paper, "Humans in the Loop, Lives on the Line," contributes the evaluation dimension: it proposes fairness, transparency, and accuracy as the testable properties of human-in-the-loop systems in high-risk settings. We intend to borrow this framing directly in our evaluation plan; the system will be judged on whether it flags consistently, explains traceably, and never coerces.

### 4.4 Theme Four: privacy obligations under Indian law

The final strand of the review is privacy. The Springer-published analysis of the DPDP Act 2023 in the healthcare context examines consent, data localization, and sector-specific obligations, and makes clear that health data and identity documents such as Aadhaar are exactly the class of personal data the Act treats most carefully. A THOA screening system will handle Aadhaar numbers, income declarations, and medical records, the DPDP Act's most protected categories. The paper's analysis of the consent architecture, in particular, has shaped our planned handling of document uploads: consent will be recorded and stored as an explicit, auditable event, not assumed from the act of submission.

---

[PAGE BREAK]

## 5. Proposed Ethical Safeguards

The safeguards below are proposals; they describe what the system will be designed to do, and what it will be designed to refuse to do.

**First, no numeric scoring of subjective standards.** The system will extract facts from the Form 3 affidavit, entities, dates, stated relationship duration, named events, and will present them to the committee as facts. It will not compute a sentiment score, an affection score, or any other quantification of relationship legitimacy. Cases of this type will always be routed to the committee in a state of pending human review, regardless of how complete their documentation is. This safeguard is borrowed directly from the AJOB finding discussed in Section 4.3: the moment a relationship is reduced to a number, the number becomes optimizable, and the law's safeguard is silently hollowed out.

**Second, mandatory human review for every ambiguous route.** Non-relative cases, foreign-national cases, and any case that trips an anomaly will not be cleared automatically. The rule engine's best possible outcome is PENDING_COMMITTEE_REVIEW; the system is structurally incapable of producing an approval. This is enforced in the data model itself, not merely in the interface, so that no future refactor or configuration change can accidentally turn the system into a decision-maker.

**Third, overrides with a paper trail.** Any committee member who overrides a system flag will be required to record a written justification, which will be logged immutably. The audit log, uploads, screenings, overrides, decisions, will be append-only by design, so that every action on a case can be reconstructed later, including who acted, when, and why.

**Fourth, the system will never decide.** The proposed tool is a verification and flagging instrument. It will not opine on medical fitness beyond confirming that certification exists, and it will not opine on the ethics of any case. Its outputs are inputs to judgment, never substitutes for it.

---

[PAGE BREAK]

## 6. Anticipated Challenges and Limitations

A proposal that does not name its own limits is not credible, so we state ours plainly.

**Document authenticity.** The proposed system verifies that a document exists, is internally consistent, and matches the schema. It does not, and cannot, detect a sophisticated forgery. A Form 21 that is fabricated at high quality will pass the same checks as a genuine one. This is an inherent limit of content-based screening, and it means the committee's residual human verification of document provenance remains essential. We do not claim to close this gap; we claim only that the system concentrates human attention on the cases and documents where it matters most.

**Regional-language handwriting.** OCR and extraction accuracy on handwritten affidavits in Hindi, Marathi, and other regional languages is an open problem in the literature, and we do not claim to have solved it. The proposed pipeline will flag low-confidence extractions for human review rather than guess, but handwritten regional-language documents will remain the weakest link in the chain, and the evaluation plan will measure extraction accuracy on them separately from everything else.

**Calibration of risk thresholds.** The income-disparity check is a case in point. The Act does not state a numerical disparity threshold, so any threshold we choose, for instance a ratio between donor and recipient income, is a heuristic drawn from fraud-detection literature, not from statute. We propose that any such threshold be calibrated by a legal or domain expert before real-world use. A student team choosing a number on its own would be overstepping, and we treat that boundary as a governance question, not a coding detail.

**Automation bias.** Finally, there is the risk that a busy committee will come to trust the system's "clean" verdicts and review less carefully, the rubber-stamp failure mode documented in the human-in-the-loop literature. The safeguards in Section 5 are designed to mitigate this, but they cannot eliminate it; awareness of the risk is itself part of the mitigation, and we intend to make the dashboard's design deliberately unquiet, with flags and legal citations front and center, rather than a single reassuring verdict.

---

[PAGE BREAK]

## 7. Data Privacy Considerations

Because the system will handle Aadhaar numbers, PAN numbers, income declarations, and medical records, it must be designed for India's Digital Personal Data Protection Act, 2023, from the start rather than retrofitted later. Figure 3 summarizes the proposed data-flow controls.

[FIGURE: privacy]

*Figure 3: Proposed data-flow controls across the system lifecycle, aligned with DPDP Act expectations.*

**Masking.** Aadhaar and PAN numbers will be masked to the last four digits in every non-administrative view, including committee-facing dashboards and generated reports. Full values will exist only in encrypted storage and will be decrypted only when a specific legal or administrative workflow requires it.

**Access control.** Access will be role-based: administrators, reviewers, and viewers will see different levels of data, and reviewers will see only the cases assigned to them. The principle is least privilege, applied by design rather than by convention.

**Audit logging.** Every action, upload, screening, override, decision, even report generation, will be logged with actor, timestamp, and action, in an append-only log. The audit trail is not a compliance afterthought; it is the system's answer to the DPDP Act's accountability requirements.

**Consent.** Uploading a case's documents will require a recorded consent event, stored as a structured record, so that the basis for processing each piece of personal data is demonstrable. The consent record itself will be versioned, so that if the terms of processing change, the system can show which consent governed which period of processing.

**Encryption and retention.** Data will be encrypted at rest and in transit, following the standard practice of transport-layer encryption for all API traffic and application-layer encryption for identity fields before they reach the database. Retention will be configurable and aligned with clinical and legal record-keeping norms, with automatic archiving after the case lifecycle closes.

These are planned measures, and they will be subject to review by the faculty and, in a real deployment, by a legal professional qualified under the DPDP Act.

---

[PAGE BREAK]

## 8. Inference: What This Research Taught Us

Having worked through these ten sources, I want to record what changed in my own understanding, because some of it surprised me.

The biggest legal gap this research surfaced is not in the text of the Act, it is in the machinery between the text and the transplant. The Act's requirements are, if anything, over-specified; Mathew's comparison shows India's framework is stricter on paper than the systems of countries we instinctively compare ourselves to. The gap is that enforcement depends entirely on committees reading fifteen to twenty documents by hand, under judicial deadlines, with penalties hanging over them. Every one of the papers that examined the enforcement side, LiveLaw, Legal Service India, the Zenodo case studies, arrived at the same point by different routes: the law is not being broken at the drafting stage; it is being strained at the application stage. That reframed my view of what our project actually is. I started with the technical framing, a document-processing pipeline. I ended with the regulatory one: a proposal to make an existing law enforceable in practice, at scale, without changing who decides.

On the question of where human judgment must remain irreplaceable, the literature confirmed a position I held only vaguely at the start. The AJOB paper made me see that "affection and attachment" is not a piece of information that can be extracted, like a date of birth. It is a judgment the law deliberately assigns to people who can look at a donor and hear the donor speak. Reducing it to a score would not merely be a poor engineering trade-off; it would be a quiet repeal of Section 9(3)'s safeguard, because a number can be optimized for, and a human judgment cannot. The same logic applies downstream: the committee is not a fallback for a broken automation; it is the point of the exercise.

The open question I would put to a domain expert before this system could move past proposal stage concerns the threshold rules. The Act specifies the documents, but it does not specify the mathematics: what income disparity is suspicious, what period of known relationship is significant, what constitutes a red flag. A legal professional's answer to how these thresholds should be set, and who should own them after deployment, is a precondition for this system to be more than a student project. Until that question is answered by someone with authority over the law, our heuristics remain exactly what they are: heuristics.

This review taught me that the hard part of this project was never the OCR, and was never the rules. It is the discipline of knowing where the system's authority ends. That is the design constraint I will carry into the build, and it is the reason I am confident proposing a system whose entire job is to prepare a human decision it is forbidden from making.
