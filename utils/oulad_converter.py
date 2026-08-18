

import pandas as pd
import os

OULAD_DIR        = "oulad_data"
VLE_FILE         = os.path.join(OULAD_DIR, "studentVle.csv")
ASSESSMENT_FILE  = os.path.join(OULAD_DIR, "studentAssessment.csv")
STUDENT_FILE     = os.path.join(OULAD_DIR, "studentInfo.csv")
OUTPUT_FILE      = "student_activity.csv"


TARGET_MODULE    = "BBB"       
TARGET_PERIOD    = "2013J"      


def convert():
    print("Loading OULAD files...")

    # ── Load student info ────────────────────────────────────────────
    students = pd.read_csv(STUDENT_FILE)
    students = students[
        (students["code_module"]       == TARGET_MODULE) &
        (students["code_presentation"] == TARGET_PERIOD)
    ][["id_student", "code_module"]].copy()

    
    students["name"]   = "Student_" + students["id_student"].astype(str)
    students["email"]  = "s" + students["id_student"].astype(str) + "@university.edu"
    students["course"] = students["code_module"].map({
        "AAA": "Social Sciences",
        "BBB": "Social Sciences",
        "CCC": "STEM",
        "DDD": "STEM",
        "EEE": "STEM",
        "FFF": "STEM",
        "GGG": "Social Sciences",
    })

    print(f"  Students loaded: {len(students)}")

   
    vle = pd.read_csv(VLE_FILE)
    vle = vle[
        (vle["code_module"]       == TARGET_MODULE) &
        (vle["code_presentation"] == TARGET_PERIOD)
    ][["id_student", "date", "sum_click"]].copy()

   
    vle_daily = (
        vle.groupby(["id_student", "date"])
        .agg(
            login_count     = ("sum_click", lambda x: min(int(x.sum() / 10), 5)),
            session_minutes = ("sum_click", lambda x: float(min(x.sum() * 2, 180)))
        )
        .reset_index()
    )


    import datetime
    start_date = datetime.date.today() - datetime.timedelta(days=60)
    vle_daily["date"] = vle_daily["date"].apply(
        lambda d: (start_date + datetime.timedelta(days=int(d))).strftime("%Y-%m-%d")
    )

    print(f"  VLE daily rows: {len(vle_daily)}")

    # ── Load assessments (quiz scores) ───────────────────────────────
    assessments = pd.read_csv(ASSESSMENT_FILE)
    assessments = assessments[["id_student", "date_submitted", "score", "is_banked"]].copy()
    assessments = assessments[assessments["is_banked"] == 0]   # exclude banked credits
    assessments = assessments.rename(columns={
        "date_submitted": "date",
        "score":          "quiz_score"
    })

    assessments["date"] = assessments["date"].apply(
        lambda d: (start_date + datetime.timedelta(days=int(d))).strftime("%Y-%m-%d")
        if pd.notna(d) else None
    )
    assessments = assessments.dropna(subset=["date"])
    assessments["submitted"] = 1  

    assessments_daily = (
        assessments.groupby(["id_student", "date"])
        .agg(quiz_score=("quiz_score", "mean"), submitted=("submitted", "max"))
        .reset_index()
    )

    print(f"  Assessment rows: {len(assessments_daily)}")

   
    merged = vle_daily.merge(assessments_daily, on=["id_student", "date"], how="left")
    merged = merged.merge(students[["id_student", "name", "email", "course"]],
                          on="id_student", how="inner")

  
    merged["quiz_score"] = merged["quiz_score"].fillna("")
    merged["submitted"]  = merged["submitted"].fillna(0).astype(int)

   
    output = merged[[
        "name", "email", "course", "date",
        "login_count", "session_minutes", "quiz_score", "submitted"
    ]]

    
    top_students = output["email"].unique()[:500]
    output = output[output["email"].isin(top_students)]

    output.to_csv(OUTPUT_FILE, index=False)
    print(f"\n  Done! Saved {len(output)} rows to {OUTPUT_FILE}")
    print(f"  Students included: {output['email'].nunique()}")
    print(f"  Upload this file at: http://127.0.0.1:8000/upload")


if __name__ == "__main__":
    convert()