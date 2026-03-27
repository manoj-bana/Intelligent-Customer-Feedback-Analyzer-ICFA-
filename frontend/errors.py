ERROR_MESSAGES = {
    # ── Username ──
    "USERNAME_REQUIRED":        "Username is required",
    "USERNAME_TAKEN":           "Username already exists",
    "USERNAME_AVAILABLE":       "Username available",

    # ── Email ──
    "EMAIL_REQUIRED":           "Email is required",
    "EMAIL_INVALID_FORMAT":     "Invalid email format",
    "EMAIL_TAKEN":              "Email already registered",
    "EMAIL_AVAILABLE":          "Email available",

    # ── Password ──
    "PASSWORD_REQUIRED":        "Password is required",
    "PASSWORD_WEAK":            "Password does not meet all requirements (see checklist above)",
    "PASSWORD_MISMATCH":        "Passwords do not match",
    "PASSWORD_MATCH":           "Passwords match",
    "PASSWORD_CONFIRM_REQUIRED":"Please confirm your password",
    "PASSWORD_REQUIREMENTS":    "Password does not meet all requirements",
    "PASSWORD_FIELDS_REQUIRED": "Both password fields are required",

    # ── Security Answer ──
    "ANSWER_REQUIRED":          "Security answer is required",

    # ── Login ──
    "LOGIN_FIELDS_REQUIRED":    "Username and password are required",
    "INVALID_LOGIN":            "Invalid credentials",
    "BACKEND_OFFLINE":          "Backend offline. Start the server and try again.",

    # ── Register ──
    "REGISTER_FAILED":          "Registration failed",
    "BACKEND_UNREACHABLE":      "Backend not reachable. Run: `uvicorn backend.main:app --reload --port 8000`",
    "UNEXPECTED_ERROR":         "An unexpected error occurred",

    # ── Forgot Password ──
    "FORGOT_USERNAME_REQUIRED": "Please enter your username",
    "FORGOT_USER_NOT_FOUND":    "User not found",
    "FORGOT_ANSWER_REQUIRED":   "Please enter your answer",
    "FORGOT_WRONG_ANSWER":      "Incorrect answer",
    "FORGOT_RESET_FAILED":      "Reset failed",
    "FORGOT_FIELDS_REQUIRED":   "Both password fields are required",
    "FORGOT_RESET_SUCCESS":     "Password reset successfully! Please sign in.",
    "FORGOT_SERVICE_ERROR":     "Service error",
}