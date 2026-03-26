def compose_email(recipient, subject, body):
    """
    Compose an email with the given recipient, subject, and body.

    :param recipient: The email address of the recipient.
    :param subject: The subject of the email.
    :param body: The body of the email.
    :return: A formatted email string.
    """
    email_message = f"To: {recipient}\nSubject: {subject}\n\n{body}"
    return email_message

# Draft the email to Olivia
recipient = "olivia@example.com"
subject = "Lawn Mower Request"
body = "I need the lawn mower by tomorrow morning."

# Compose the email
email_to_olivia = compose_email(recipient, subject, body)

# Print the composed email
def main():
    print(email_to_olivia)

if __name__ == "__main__":
    main()
