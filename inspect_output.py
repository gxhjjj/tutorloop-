import json, glob, os

output_dir = r"D:\agent-system\output\亲戚孩子"
files = sorted(glob.glob(os.path.join(output_dir, "diagnose_*.json")), reverse=True)
if files:
    with open(files[0], "r", encoding="utf-8") as f:
        d = json.load(f)
    print("Title:", d["title"])
    print("Grade:", d.get("grade"), "| Textbook:", d.get("textbook"))
    print("Questions:", len(d["questions"]))
    print()
    for q in d["questions"][:5]:
        content = q["content"][:100]
        print(f"  {q['q_id']} [{q['part']}|{q['type']}]")
        print(f"    Q: {content}...")
        print(f"    A: {q['answer']} | Tests: {q['test_point']}")
        print(f"    Signal: {q['weak_point_signal']}")
        print()
    print(f"... and {len(d['questions'])-5} more questions")
