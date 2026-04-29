def prompts_i18n_template():

    handle_capx_app_path = r"gpt_gateway/prompts/template_i18n.md"

    try:
        with open(handle_capx_app_path, "r", encoding="utf-8") as file:
            handle_meeting_template = file.read()
    except FileNotFoundError:
        print("File not found:", handle_capx_app_path)
        return None
    
    prompts_template = handle_meeting_template
    
    return prompts_template
