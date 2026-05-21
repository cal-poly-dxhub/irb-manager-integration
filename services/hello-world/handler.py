from dx_say_hello import say_hello


def handler(event, context):
    return {
        "statusCode": 200,
        "body": say_hello("Lambda"),
    }
