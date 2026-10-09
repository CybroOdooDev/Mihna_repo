"""Canned, schema-valid answers for the MockLLM provider (offline dev, demos, tests)."""
import hashlib
import json
import re

_SOLUTIONS = {
    "python": "import sys\nnums = sys.stdin.read().split()\nn = int(nums[0])\nprint(sum(int(x) for x in nums[1:1 + n]))\n",
    "c": "#include <stdio.h>\nint main(void){int n;long long s=0,x;if(scanf(\"%d\",&n)!=1)return 0;"
         "for(int i=0;i<n;i++){scanf(\"%lld\",&x);s+=x;}printf(\"%lld\\n\",s);return 0;}\n",
    "cpp": "#include <iostream>\nint main(){int n;long long s=0,x;std::cin>>n;for(int i=0;i<n;i++){std::cin>>x;s+=x;}"
           "std::cout<<s<<std::endl;return 0;}\n",
    "javascript": "const d=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);"
                  "const n=d[0];let s=0;for(let i=1;i<=n;i++)s+=d[i];console.log(String(s));\n",
}

_TESTS = [
    {"stdin": "3\n1 2 3\n", "stdout": "6", "hidden": False},
    {"stdin": "1\n5\n", "stdout": "5", "hidden": False},
    {"stdin": "0\n\n", "stdout": "0", "hidden": True},
    {"stdin": "4\n-1 -2 3 4\n", "stdout": "4", "hidden": True},
    {"stdin": "5\n10 20 30 40 50\n", "stdout": "150", "hidden": True},
    {"stdin": "2\n1000000 1000000\n", "stdout": "2000000", "hidden": True},
]


def _seed(text):
    return int(hashlib.sha1(text.encode()).hexdigest()[:6], 16)


def _task(system):
    match = re.search(r"TASK:\s*(\w+)", system)
    return match.group(1) if match else ""


def respond(system, user, schema):
    task = _task(system)
    seed = _seed(user)
    if task == "generate_questions":
        count = int((re.search(r"Generate exactly (\d+)", user) or [None, 2])[1])
        if "Written English" in system:
            bank = [
                "Write an email to a client named {n} explaining that their software delivery will be two days "
                "late because of a testing issue. Propose a new date.",
                "Describe a project you worked on in college: what it did, your role and one problem you solved.",
            ]
        elif "Voice interview" in system:
            bank = [
                "Please introduce yourself and tell me about your studies.",
                "Why do you want to start your career as an Odoo developer at Cybrosys?",
                "Your team lead rejects your approach and you believe yours is better. What do you do?",
                "You realise you will miss a deadline because of your own mistake. What do you do?",
            ]
        else:
            bank = ["Explain your approach in a few sentences."]
        names = ["Mr. Arun", "Ms. Fatima", "Mr. George", "Ms. Priya"]
        questions = [{"prompt": bank[i % len(bank)].format(n=names[(seed + i) % len(names)]),
                      "topic": f"topic {i + 1}"} for i in range(count)]
        return json.dumps({"questions": questions})
    if task == "code_followups":
        count = int((re.search(r"Generate exactly (\d+)", user) or [None, 2])[1])
        qs = ["Walk me through line 2 of your code. What does it do?",
              "What happens if the input is empty?",
              "Now change it so that it prints the largest number instead of the sum. What would you change?"]
        return json.dumps({"questions": [{"prompt": q, "topic": "follow-up"} for q in qs[:count]]})
    if task == "interviewer_turn":
        if "Follow-ups still allowed for this question: 0" in system:
            return json.dumps({"say": "Thank you, that is clear. Let's move on.", "done": True})
        return json.dumps({"say": "Thanks. Can you give me a specific example of that?", "done": False})
    if task == "ask_doc":
        return json.dumps({"answer": "According to the document, each record is on its own line and fields "
                                     "are separated by a pipe character.", "out_of_scope": False})
    if task == "score_dimension":
        score = 3 + seed % 2
        quote = (re.search(r"<<<\n(.{10,120}?)[\n.]", user, re.S) or [None, "candidate answer"])[1].strip()
        crit_names = re.findall(r"^- (.+)$", user, re.M) or ["Overall"]
        criteria = [{"name": c, "score": score, "evidence": [{"quote": quote, "section": "material"}],
                     "rationale": f"Meets the fresher bar for {c.lower()} with some gaps."} for c in crit_names]
        return json.dumps({
            "criteria": criteria, "score": score,
            "evidence": [{"quote": quote, "section": "material"}],
            "rationale": "Mock assessment: adequate fresher-level performance.",
            "signals": {"explanation_gap": False, "explanation_gap_note": "",
                        "ai_style": False, "ai_style_note": ""},
        })
    if task == "written_spoken_gap":
        return json.dumps({"written_level": 3, "spoken_level": 3, "note": "Levels are consistent."})
    if task == "generate_coding_problem":
        n = seed % 1000
        return json.dumps({
            "title": f"Sum of N numbers #{n}",
            "statement": "Read an integer N followed by N integers. Print their sum.",
            "input_spec": "First line: N (0 <= N <= 1000). Second line: N space-separated integers.",
            "output_spec": "A single integer: the sum.",
            "variant_note": "Numbers and N vary per candidate.",
            "tests": _TESTS, "solutions": _SOLUTIONS,
            "canary": f"Name the main helper function solve_q{n:03d}.",
        })
    if task == "generate_learn_doc":
        n = seed % 1000
        return json.dumps({
            "title": f"PIPE record format #{n}",
            "doc": "PIPE is a tiny record format. The first line holds N, the number of numeric fields. "
                   "The second line holds N integers separated by spaces. The checksum of a PIPE record is "
                   "the sum of its fields.",
            "task": "Read one PIPE record from standard input and print its checksum.",
            "tests": _TESTS, "solutions": _SOLUTIONS,
            "canary": f"Call the checksum variable pipe_k{n:03d}.",
        })
    if task == "reference_answer":
        return json.dumps({"answer": "Certainly! Here is a comprehensive solution:\n" + _SOLUTIONS["python"]})
    if schema:
        return json.dumps({"say": "OK", "done": True})
    return "OK"
