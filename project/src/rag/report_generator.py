from .retriever import retrieve_knowledge
from .generator import generate_report

def create_report(confidence):
    knowledge = retrieve_knowledge()
    report = generate_report(confidence, knowledge)

    with open("outputs/reports/report.txt", "w") as f:
        f.write(report)

    print("Clinical report generated.")
