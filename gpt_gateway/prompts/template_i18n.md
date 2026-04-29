### **Image-Based Localization Compliance Analysis (Perception Phase)**  

To ensure a more structured and efficient evaluation, we will first **analyze localization issues** in the image for only the non-compliant controls. 

**Goal**: Identify localization issues directly from the image, without extracting control coordinates initially.  
**Actions**:  
- **Detect UI text elements** (auto detect).
- Auto-detect language ID (e.g., German (DE), French (FR) and so on) 
- Focus on the topmost window in the image to avoid irrelevant detections.
- If the topmost window is tree or tab structure, need to analyze the content and the label of info text of it.
- Analyze localization issues:
  - **Translate**: Check if the text whether translate.
  - **Text Truncation**: Identify whether the text or sentence is truncated, cut off, or not fully displayed. If the text is located under a window or dialog, it should be fully visible and not truncated.
  - **Element Overlap**: Confirm that UI elements do not overlap (e.g., text over buttons, icons on top of labels).
  - **Text Overflow**: Check if text strings are overflowing beyond their designated containers (e.g., overflowing past edges or overlapping into neighboring controls). **Exception**: Tooltip dialogs, popup menus, or overlay dialogs that appear on top of other UI elements are intentional design patterns and should NOT be flagged as overflow issues.
  - **UI Control Borders**: Ensure all borders or outlines are visible and not clipped.  
  - **Localization Accuracy**: Evaluate the correctness of the translation.  

---


### **IMPORTANT INSTRUCTIONS**: 
- **Only analyze UI text and localization issues**. 
- **Output should be a structured Markdown table**—NO extra explanations, NO additional text. 

---
### **Expected Output Format**  
The Image column, please keep it as it is, it is my hard code string, **DO NOT** make assumptions.
The result should be returned in a **Markdown table format** for structured presentation, **only table, no others**.
**Markdown Table Format:**
| Order | EN | Language: **{{Language Id}}** | Localization Compliance | Issues | Suggestions for Improvement |
|-----------|-------------|-------------|------------------------|----------------------------|----------------------------|
| 1 | (English text) | (Localized translation) | (✅ Compliant or ❌ Non-compliant) | (Issues) | (Suggestions) |


**Examples for Reference:**
| Order | EN | Language: **{{Language Id}}** | Localization Compliance | Issues | Suggestions for Improvement |
|-----------|-------------|-------------|------------------------|----------------------------|----------------------------|
| 1 | Mute (Ctrl + M) | (Ctrl + M) stummschalten | ❌ Non-compliant | Word Order is wrong | In German, "Stummschalten" (mute) is a verb and is typically capitalized when used as a button label or at the beginning of a sentence. The current translation puts the shortcut ("Ctrl + M") before the action, which feels unnatural in German.|
| 2 | Invite and remind | Invite and remind | ❌ Non-compliant | No translate | The correct German translation of "Invite and remind" could be Einladen und Erinnern|
| 3 | Save | Speichern | ✅ Compliant | N/A | N/A |
| 4 | A I's meeting | A I's meeting | ✅ Compliant | This is a meeting name (proper noun) by design, and translation is not required. |
| 5 | tony's meeting | tony's meeting | ✅ Compliant | This is a meeting name (proper noun) by design, and translation is not required. |
| 6 | Waiting for others to join...   | Warten auf Beitritt anderer Teilnehmer ...  | ✅ Compliant | The translation is semantically complete and correctly retains the intended ellipsis ("...").|
| 7 | Only... | Nur ei... | ❌ Non-compliant | Text Truncation | This is semantically incomplete. The text "Nur ei..." appears truncated.Correct wording could not be fully extracted|
| 8 | Start Slido (polling and Q&A) | Slido starten (Umfragen und Frage-und-Antwort | ❌ Non-compliant | Truncated text | Increase area/make the font size smaller to show the whole text or adjust the solution or replace with a more concise UI |