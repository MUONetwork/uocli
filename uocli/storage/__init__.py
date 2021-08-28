from botocore.client import Config
from uocli import config
from uocli.storage.session import assumed_session


class S3(object):
    """
    Convenience wrapper for an S3 object.
    To use this in your code:
    from uocli.storage import S3
    s3 = S3()
    bucket_name = "Audubon"
    prefix = "2018-07-18_night"
    bucket = s3.Bucket(bucket_name)
    # List 10 files from 2018-07-18_night key
    [x for x in bucket.objects.filter(Prefix=prefix).limit(10)]

    # Read the data (assuming this is an image, we'll use imageio as the library to read the image data)
    import plotly.express as px
    import imageio as iio
    key = "2018-07-18_night/0_d6_1531962017.png"
    raw_img = s3.Object(bucket, key).get()['Body'].read()
    img = iio.imread(raw_img)
    fig = px.imshow(img)
    fig.show()
    """

    def __new__(cls, *args, **kwargs):
        client_id = config['storage']['client_id']
        client_secret = config['storage']['client_secret']
        storage_url = config['storage']['url']
        sess = assumed_session(client_id=client_id,
                               client_secret=client_secret)
        s3 = sess.resource('s3',
                           endpoint_url=storage_url,
                           config=Config(signature_version='s3v4'),
                           region_name='us-east-1')
        return s3
