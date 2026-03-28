from main import FOAPipeline

def run_evaluation():
    print("="*60)
    print("🧪 EVALUATING SEMANTIC TAGGING BASELINE")
    print("="*60)

    # 1. Realistic Ground-Truth Dataset (Including trick questions to test false positives)
    eval_dataset = [
        {
            "id": "FOA-001",
            "title": "Advancing Deep Neural Networks for Edge Computing",
            "desc": "This grant supports the development of robust artificial intelligence algorithms designed to run on low-power IoT devices.",
            "true_tags": ["AI/Machine Learning"]
        },
        {
            "id": "FOA-002",
            "title": "Predictive Analytics in Oncology",
            "desc": "Seeking proposals that utilize machine learning and clinical data to predict health outcomes and disease progression in cancer patients.",
            "true_tags": ["AI/Machine Learning", "Biomedical/Health"] # Multi-label!
        },
        {
            "id": "FOA-003",
            "title": "Ocean Acidification Mitigation Strategies",
            "desc": "Funding for research into carbon capture technologies to promote environmental sustainability and combat climate change.",
            "true_tags": ["Climate & Environment"]
        },
        {
            "id": "FOA-004",
            "title": "Next-Gen K-12 Engineering Curriculum",
            "desc": "Aimed at improving STEM education by deploying hands-on robotics curriculum for undergraduate and high school students.",
            "true_tags": ["STEM Education"]
        },
        {
            "id": "FOA-005", # TRICK QUESTION
            "title": "Preservation of Classical Antiquities",
            "desc": "A grant to support the curation of ancient literature. Awardees must demonstrate the financial sustainability of their preservation methods.",
            "true_tags": ["Social Sciences & Humanities"] 
            # Note: The word "sustainability" is here, so a bad tagger would accidentally tag "Climate". Let's see if ours is smart enough!
        }
    ]

    pipeline = FOAPipeline()
    
    tp = 0 # True Positives: Predicted tag is correct
    fp = 0 # False Positives: Predicted tag is wrong
    fn = 0 # False Negatives: Missed a true tag

    print(f"{'FOA ID':<10} | {'True Tags':<40} | {'Predicted Tags'}")
    print("-" * 100)

    for item in eval_dataset:
        # Mock the pipeline input
        mock_data = pipeline.base_schema.copy()
        mock_data["title"] = item["title"]
        mock_data["program_description"] = item["desc"]
        
        # Run our rule-based tagger
        tagged_result = pipeline.apply_tags(mock_data)
        
        predicted_tags = set(tagged_result["tags"])
        true_tags = set(item["true_tags"])
        
        # Calculate metrics for this specific document
        tp += len(predicted_tags.intersection(true_tags))
        fp += len(predicted_tags - true_tags)
        fn += len(true_tags - predicted_tags)
        
        print(f"{item['id']:<10} | {str(list(true_tags)):<40} | {list(predicted_tags)}")

    # 3. Calculate Final Precision, Recall, and F1-Score
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("\n" + "="*60)
    print("📊 SUMMARY METRICS (Rule-Based Baseline)")
    print("="*60)
    print(f"Total Documents Evaluated: {len(eval_dataset)}")
    print(f"Precision: {precision:.2f} (When it tags a grant, how often is it correct?)")
    print(f"Recall:    {recall:.2f} (Out of all the true tags, how many did it successfully find?)")
    print(f"F1-Score:  {f1_score:.2f} (The harmonic mean of Precision and Recall)")
    print("="*60)

if __name__ == "__main__":
    run_evaluation()