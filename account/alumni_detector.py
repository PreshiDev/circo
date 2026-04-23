"""
Alumni Detection Module
Automatically detects alumni status and type based on meeting context
"""

import re

# School-related keywords and their corresponding alumni types
SCHOOL_KEYWORDS = {
    'university': {
        'keywords': ['university', 'uni', 'college', 'undergrad', 'bachelor', 'degree', 'masters', 'phd', 'doctorate'],
        'alumni_type': 'University Alumni',
        'education_level': 'tertiary'
    },
    'polytechnic': {
        'keywords': ['polytechnic', 'poly', 'hnd', 'nd', 'national diploma', 'higher national'],
        'alumni_type': 'Polytechnic Alumni',
        'education_level': 'tertiary'
    },
    'college_of_education': {
        'keywords': ['college of education', 'teachers college', 'ncc', 'teaching certificate'],
        'alumni_type': 'College of Education Alumni',
        'education_level': 'tertiary'
    },
    'secondary_school': {
        'keywords': ['secondary school', 'high school', 'grammar school', 'comprehensive', 'secondary', 'sss', 'ssce', 'waec', 'neco'],
        'alumni_type': 'Secondary School Alumni',
        'education_level': 'secondary'
    },
    'primary_school': {
        'keywords': ['primary school', 'elementary school', 'primary', 'nursery', 'kindergarten', 'basic school'],
        'alumni_type': 'Primary School Alumni',
        'education_level': 'primary'
    }
}

# Common school name patterns
SCHOOL_NAME_PATTERNS = [
    r'(?:at|from|of|in)\s+(?:the\s+)?([A-Za-z0-9\s&\'\-\.]+(?:University|College|Polytechnic|School|Academy|Institute|High School|Secondary School|Primary School|Grammar School|Comprehensive School))',
    r'([A-Za-z0-9\s&\'\-\.]+(?:University|College|Polytechnic|School|Academy|Institute))',
    r'(?:classmate|coursemate|school mate|alumni|graduate)\s+(?:from|of|at)\s+([A-Za-z0-9\s&\'\-\.]+)',
]



def extract_school_name(meeting_context):
    """
    Extract the school name from the meeting context string.
    Returns the school name or None if not found.
    """
    if not meeting_context:
        return None
    
    context_clean = meeting_context.strip()
    
    for pattern in SCHOOL_NAME_PATTERNS:
        match = re.search(pattern, context_clean, re.IGNORECASE)
        if match:
            school_name = match.group(1).strip()
            school_name = re.sub(r'\s+', ' ', school_name)
            return school_name
    
    # If no pattern matched but context contains educational keywords, return the whole context
    context_lower = context_clean.lower()
    for school_type, data in SCHOOL_KEYWORDS.items():
        if any(keyword in context_lower for keyword in data['keywords']):
            return context_clean
    
    return None



def detect_alumni(meeting_context):
    """
    Detect if the meeting context indicates an alumni connection.
    Returns (is_alumni, alumni_type, school_name)
    
    Args:
        meeting_context: String describing where/how the person was met
    
    Returns:
        tuple: (is_alumni: bool, alumni_type: str or None, school_name: str or None)
    """
    if not meeting_context:
        return False, None, None
    
    context_lower = meeting_context.lower().strip()
    is_alumni = False
    alumni_type = None
    school_name = extract_school_name(meeting_context)
    
    # Check if the context is school-related
    for school_type, data in SCHOOL_KEYWORDS.items():
        if any(keyword in context_lower for keyword in data['keywords']):
            is_alumni = True
            alumni_type = data['alumni_type']
            break
    
    # Additional checks for classmate/coursemate mentions
    classmate_keywords = ['classmate', 'coursemate', 'school mate', 'class mate', 'course mate']
    if any(keyword in context_lower for keyword in classmate_keywords):
        is_alumni = True
        
        # If we haven't determined the type yet, try to infer from the school name
        if not alumni_type:
            if school_name:
                school_lower = school_name.lower()
                for school_type, data in SCHOOL_KEYWORDS.items():
                    if any(keyword in school_lower for keyword in data['keywords']):
                        alumni_type = data['alumni_type']
                        break
            
            # Default if we can't determine
            if not alumni_type:
                alumni_type = 'School Alumni'
    
    # If school is mentioned but no specific type detected
    if school_name and not is_alumni:
        school_lower = school_name.lower()
        for school_type, data in SCHOOL_KEYWORDS.items():
            if any(keyword in school_lower for keyword in data['keywords']):
                is_alumni = True
                alumni_type = data['alumni_type']
                break
    
    # ✅ ALWAYS return 3 values
    return is_alumni, alumni_type, school_name


def get_alumni_type_display(meeting_context):
    """Get a human-readable display of the alumni relationship"""
    is_alumni, alumni_type, school_name = detect_alumni(meeting_context)
    
    if not is_alumni:
        return None
    
    if school_name:
        return f"{alumni_type} - {school_name}"
    return alumni_type


def categorize_meeting_context(meeting_context):
    """
    Categorize the meeting context for display purposes.
    Returns the category name.
    """
    if not meeting_context:
        return None
    
    context_lower = meeting_context.lower().strip()
    
    # Check if it's school-related first
    is_alumni, _, _ = detect_alumni(meeting_context)
    if is_alumni:
        return 'school'
    
    # Other categories
    categories = {
        'wedding': ['wedding', 'marriage', 'bride', 'groom'],
        'birthday': ['birthday', 'bday', 'born day'],
        'conference': ['conference', 'summit', 'meetup', 'tech'],
        'coffee_dining': ['coffee', 'cafe', 'tea', 'lunch', 'dinner', 'restaurant'],
        'party_social': ['party', 'celebration', 'club', 'bar', 'night'],
        'work': ['work', 'office', 'colleague', 'coworker'],
        'networking': ['networking', 'business', 'professional'],
        'sports_fitness': ['gym', 'fitness', 'sport', 'game', 'match'],
        'travel': ['travel', 'trip', 'vacation', 'holiday'],
        'religious': ['church', 'mosque', 'temple', 'religious', 'worship']
    }
    
    for category, keywords in categories.items():
        if any(keyword in context_lower for keyword in keywords):
            return category
    
    return 'other'