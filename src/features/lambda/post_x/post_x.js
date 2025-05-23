import { TwitterApi } from 'twitter-api-v2';
import 'dotenv/config';
import mysql from 'mysql2/promise';

// Create OAuth 1.0a User Context client
const client = new TwitterApi({
  appKey: process.env.API_KEY,
  appSecret: process.env.API_KEY_SECRET,
  accessToken: process.env.ACCESS_TOKEN,
  accessSecret: process.env.ACCESS_TOKEN_SECRET,
});

// Get the read/write client with user context
const rwClient = client.readWrite;

function formatThaiDate(date) {
  if (!date) return 'Unknown';
  
  const thaiMonths = [
    'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
    'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
  ];
  
  const d = new Date(date);
  const day = d.getDate();
  const month = thaiMonths[d.getMonth()];
  const year = d.getFullYear() + 543; // Convert to Buddhist Era
  
  return `${day} ${month} ${year}`;
}

async function getLatestMissingPerson() {
  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'admin',
    password: process.env.DB_PASSWORD || '12345678',
    database: process.env.DB_NAME || 'missing_persons_db'
  });

  try {
    const [rows] = await connection.execute(
      'SELECT * FROM missing_persons ORDER BY created_at DESC LIMIT 1'
    );
    return rows[0];
  } finally {
    await connection.end();
  }
}

async function getLatestMirrorPerson() {
  const connection = await mysql.createConnection({
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'admin',
    password: process.env.DB_PASSWORD || '12345678',
    database: process.env.DB_NAME || 'missing_persons_db'
  });

  try {
    const [rows] = await connection.execute(
      'SELECT * FROM mirror_missing_persons ORDER BY id DESC LIMIT 1'
    );
    return rows[0];
  } finally {
    await connection.end();
  }
}

async function downloadImage(url) {
  const response = await fetch(url);
  const buffer = await response.arrayBuffer();
  return Buffer.from(buffer);
}

async function verifyTwitterCredentials() {
  try {
    const me = await rwClient.v2.me();
    console.log('Twitter authentication successful. Logged in as:', me.data.username);
    return true;
  } catch (error) {
    console.error('Twitter authentication failed:', error.message);
    if (error.data) {
      console.error('Twitter API Error Details:', error.data);
    }
    return false;
  }
}

async function postTweet(text, imageUrl = null) {
  console.log('Preparing to post tweet with text:', text);
  
  try {
    if (imageUrl) {
      // Download and upload the image first
      const imageBuffer = await downloadImage(imageUrl);
      const mediaId = await rwClient.v1.uploadMedia(imageBuffer, { mimeType: 'image/jpeg' });
      
      // Post tweet with media ID
      const tweet = await rwClient.v2.tweet(text, { media: { media_ids: [mediaId] } });
      console.log('Tweet with media posted successfully:', tweet);
      return tweet;
    }

    // Post text-only tweet using v2 API
    const tweet = await rwClient.v2.tweet(text);
    console.log('Text-only tweet posted successfully:', tweet);
    return tweet;
  } catch (error) {
    console.error('Error posting tweet:', error.message);
    if (error.data) {
      console.error('Twitter API Error Details:', error.data);
    }
    throw error;
  }
}

function removeThaiHonorific(name) {
  if (!name) return 'ไม่ระบุ';
  
  const honorifics = [
    'นาย', 'นาง', 'นางสาว', 'ด.ช.', 'ด.ญ.', 'เด็กชาย', 'เด็กหญิง',
    'คุณ', 'คุณนาย', 'คุณหญิง', 'คุณแม่', 'คุณพ่อ', 'คุณปู่', 'คุณย่า',
    'คุณตา', 'คุณยาย', 'คุณลุง', 'คุณป้า', 'คุณน้า', 'คุณอา'
  ];
  
  let processedName = name.trim();
  for (const honorific of honorifics) {
    if (processedName.startsWith(honorific)) {
      processedName = processedName.substring(honorific.length).trim();
      break;
    }
  }
  
  return processedName || 'ไม่ระบุ';
}

async function createMainSystemTweet(missingPerson) {
  if (!missingPerson) return null;
  
  const tweetText = [
    '🚨 แจ้งคนหาย 🚨',
    '',
    '📌 ข้อมูลจากระบบหลัก:',
    `ชื่อ-สกุล: ${removeThaiHonorific(missingPerson.full_name)}`,
    `อายุ: ${missingPerson.age_missing || 'ไม่ระบุ'} ปี`,
    `เพศ: ${missingPerson.gender || 'ไม่ระบุ'}`,
    `สถานที่หายตัว: ${missingPerson.missing_location || 'ไม่ระบุ'}`,
    `วันที่หายตัว: ${formatThaiDate(missingPerson.missing_date)}`,
    `แหล่งที่มา: ${missingPerson.source_url}`
  ].join('\n');

  return postTweet(tweetText, missingPerson.photo_url);
}

async function createMirrorSystemTweet(mirrorPerson) {
  if (!mirrorPerson) return null;
  
  const tweetText = [
    '🚨 แจ้งคนหาย 🚨',
    '',
    '📌 ข้อมูลจากระบบสำรอง:',
    `ชื่อ-สกุล: ${removeThaiHonorific(mirrorPerson.full_name || 'ไม่ระบุ')}`,
    `อายุ: ${mirrorPerson.age || 'ไม่ระบุ'} ปี`,
    `รายละเอียด: ${mirrorPerson.detail_text ? `${mirrorPerson.detail_text.substring(0, 100)}...` : 'ไม่ระบุ'}`,
    `แหล่งที่มา: ${mirrorPerson.source_url || 'ไม่ระบุ'}`
  ].join('\n');

  return postTweet(tweetText, mirrorPerson.photo_url);
}

(async () => {
  try {
    // Verify Twitter credentials first
    const isAuthenticated = await verifyTwitterCredentials();
    if (!isAuthenticated) {
      console.error('Failed to authenticate with Twitter. Please check your API credentials.');
      process.exit(1);
    }

    // Get latest records from both databases
    const missingPerson = await getLatestMissingPerson();
    const mirrorPerson = await getLatestMirrorPerson();
    
    if (!missingPerson && !mirrorPerson) {
      console.log('No missing person records found');
      return;
    }

    // Post separate tweets for each system
    if (missingPerson) {
      try {
        const mainTweet = await createMainSystemTweet(missingPerson);
        console.log('Main system tweet posted successfully');
      } catch (error) {
        console.error('Failed to post main system tweet:', error.message);
      }
    }

    if (mirrorPerson) {
      try {
        const mirrorTweet = await createMirrorSystemTweet(mirrorPerson);
        console.log('Mirror system tweet posted successfully');
      } catch (error) {
        console.error('Failed to post mirror system tweet:', error.message);
      }
    }

    console.log('Tweet posting process completed');
  } catch (error) {
    console.error('Fatal error:', error.message);
    if (error.data) {
      console.error('Twitter API Error Details:', error.data);
    }
    process.exit(1);
  }
})();