
def prompts_template(test_scenario):

    handle_capx_app_path = r"gpt_gateway/prompts/template.md"

    try:
        with open(handle_capx_app_path, "r", encoding="utf-8") as file:
            handle_meeting_template = file.read()
    except FileNotFoundError:
        print("File not found:", handle_capx_app_path)
        return None
    
    prompts_template = handle_meeting_template.format(test_scenario=test_scenario)
    
    return prompts_template

def prompts_template_performance(performance_data):
    """
    Generate performance analysis prompt using the performance template
    
    Args:
        performance_data (str): Performance report data in markdown table format
        
    Returns:
        str: Formatted prompt for performance analysis
    """
    performance_template_path = r"gpt_gateway/prompts/template_performance.md"

    try:
        with open(performance_template_path, "r", encoding="utf-8") as file:
            performance_template = file.read()
    except FileNotFoundError:
        print("File not found:", performance_template_path)
        return None
    
    # Combine the template with the performance data
    full_prompt = f"{performance_template}\n\n**Performance Data to Analyze:**\n\n{performance_data}"
    
    return full_prompt
