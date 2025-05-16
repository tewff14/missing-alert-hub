import { TwitterApi } from 'twitter-api-v2';
import 'dotenv/config';

const client = new TwitterApi({
  appKey: process.env.API_KEY,
  appSecret: process.env.API_KEY_SECRET,
  accessToken: process.env.ACCESS_TOKEN,
  accessSecret: process.env.ACCESS_SECRET,
});

// You need the read/write “wrapped” client:
const rwClient = client.readWrite;

(async () => {
  // 1) Upload the image (v1.1)
  const mediaId = await rwClient.v1.uploadMedia('./your-image.png');
  
  // 2) Post the tweet with media
  const { data: tweet } = await rwClient.v2.tweet(
    "Bot posting an image!",
    { media: { media_ids: [mediaId] } }
  );
  
  console.log("Posted tweet:", tweet);
})();