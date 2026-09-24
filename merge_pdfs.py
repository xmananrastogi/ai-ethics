from pypdf import PdfReader, PdfWriter
import os

writer = PdfWriter()

base_report = "reports/case_study_2.pdf"
ppt_report = "/Users/mananrastogi/Downloads/brave downloads/us/AI_Ethics_Copilot_THOA_Review2_Official (1).pdf"

print(f"Adding {base_report}")
writer.append(base_report)

print(f"Adding PPT: {ppt_report}")
writer.append(ppt_report)

out_file = "reports/Manan_Case_Study_2_Final_v4.pdf"
writer.write(out_file)
writer.close()

print(f"Successfully generated {out_file}")
