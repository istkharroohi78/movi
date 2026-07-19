import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp
import re
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()


@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cancelling Indexing")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been decliened by our moderators.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [
                InlineKeyboardButton('Yes',
                                     callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('close', callback_data='close_data'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>\n\nɴᴇᴇᴅ sᴇᴛsᴋɪᴘ 👉🏻 /setskip',
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure iam an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [
            InlineKeyboardButton('Accept Index',
                                 callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('Reject Index',
                                 callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        temp.CURRENT = int(skip)
        logger.info(f"🔧 SETSKIP: Updated temp.CURRENT to {temp.CURRENT}")
        await message.reply(f"Successfully set SKIP number as {skip}\nNext indexing will start from message ID {skip}")
    else:
        await message.reply("Give me a skip number")


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    current = 0

    async with lock:
        try:
            temp.CANCEL = False

            # Use individual message fetching for bot compatibility
            message_id = temp.CURRENT  # Start from skip number set by /setskip command
            processed_count = 0
            logger.info(f"🚀 INDEXING: Starting indexing from message ID {message_id} (temp.CURRENT = {temp.CURRENT})")

            while message_id <= lst_msg_id:
                if temp.CANCEL:
                    await msg.edit(f"Successfully Cancelled!!\n\nSaved <code>{total_files}</code> files to dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>")
                    break

                try:
                    # Get individual message by ID
                    message = await bot.get_messages(chat_id=chat, message_ids=message_id)

                    # Move to next message ID
                    message_id += 1
                    current += 1

                    # Update progress every 80 messages
                    if current % 80 == 0:
                        try:
                            # Calculate progress percentage based on actual message IDs
                            progress_percent = round((message_id / lst_msg_id) * 100, 1)
                            progress_bar = "█" * int(progress_percent // 5) + "░" * (20 - int(progress_percent // 5))
                            
                            can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                            reply = InlineKeyboardMarkup(can)
                            
                            progress_text = (
                                f"📊 **Indexing Progress: {progress_percent}%**\n"
                                f"[{progress_bar}]\n\n"
                                f"📁 **Current Message ID:** {message_id}/{lst_msg_id}\n"
                                f"🚀 **Started from:** {temp.CURRENT}\n"
                                f"💾 **Files Saved:** <code>{total_files}</code>\n"
                                f"🔄 **Duplicates Skipped:** <code>{duplicate}</code>\n"
                                f"🗑️ **Deleted Messages:** <code>{deleted}</code>\n" 
                                f"📄 **Non-Media Messages:** <code>{no_media + unsupported}</code>\n"
                                f"⚠️ **Unsupported Media:** <code>{unsupported}</code>\n"
                                f"❌ **Errors:** <code>{errors}</code>"
                            )
                            
                            await msg.edit_text(text=progress_text, reply_markup=reply)
                        except Exception as progress_error:
                            # Fallback to simple progress if formatting fails
                            await msg.edit_text(
                                text=f"Processing... {current}/{lst_msg_id} messages\nFiles saved: {total_files}",
                                reply_markup=reply
                            )

                    # Check if message exists and is not empty
                    if not message or message.empty:
                        deleted += 1
                        continue

                    # Check if message has media
                    if not message.media:
                        no_media += 1
                        continue

                    # Check if media type is supported
                    if message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                        unsupported += 1
                        continue

                    # Get media object
                    media = getattr(message, message.media.value, None)
                    if not media:
                        unsupported += 1
                        continue

                    # Set media properties
                    media.file_type = message.media.value
                    media.caption = message.caption

                    # Save file to database
                    aynav, vnay = await save_file(bot, media)
                    if aynav:
                        total_files += 1
                    elif vnay == 0:
                        duplicate += 1
                    elif vnay == 2:
                        errors += 1

                except Exception as e:
                    logger.exception(f"Error processing message {message_id}: {e}")
                    errors += 1
                    # Continue to next message even if current one fails
                    continue

        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            await msg.edit(f'Successfully saved <code>{total_files}</code> to dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>')


# ==========================================
# AUTO INDEXING FEATURE
# ==========================================

INDEX_CHANNEL_ID = -1003910381589

@Client.on_message(filters.chat(INDEX_CHANNEL_ID) & (filters.document | filters.video | filters.audio))
async def auto_index_channel(client, message):
    """Automatically index new media files posted and log the status"""
    try:
        # Verify message has supported media
        if not message.media or message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
            return

        # Get the media object (document, video, or audio)
        media = getattr(message, message.media.value, None)
        if not media:
            return

        # Set required properties to match how manual indexing works
        media.file_type = message.media.value
        media.caption = message.caption
        
        file_name = getattr(media, 'file_name', 'Unknown_File')
        
        logger.info(f"📥 AUTO-INDEX: Found new file '{file_name}' in channel. Saving...")
        
        # Save directly to database using your existing imported function
        aynav, vnay = await save_file(client, media)
        
        status_text = ""
        if aynav:
            status_text = "✅ **Successfully Saved**"
            logger.info(f"✅ AUTO-INDEX SUCCESS: '{file_name}' saved to database.")
        elif vnay == 0:
            status_text = "🔄 **Skipped (Duplicate)**"
            logger.info(f"🔄 AUTO-INDEX SKIPPED: '{file_name}' is already in the database (Duplicate).")
        elif vnay == 2:
            status_text = "❌ **Failed (Error)**"
            logger.error(f"❌ AUTO-INDEX FAILED: Database error while saving '{file_name}'.")
            
        # Send details to the Log Group (LOG_CHANNEL)
        try:
            log_msg = (
                f"**⚡ Auto-Index Report**\n\n"
                f"**📁 File Name:** `{file_name}`\n"
                f"**💬 Message ID:** `{message.id}`\n"
                f"**📢 Channel ID:** `{message.chat.id}`\n"
                f"**📊 Status:** {status_text}"
            )
            
            # Generate a link to the message for easy access
            link = message.link if message.link else f"https://t.me/c/{str(message.chat.id)[4:]}/{message.id}"
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Message", url=link)]])
            
            await client.send_message(
                chat_id=LOG_CHANNEL, 
                text=log_msg,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send Auto-Index log to LOG_CHANNEL: {e}")
            
    except Exception as e:
        logger.exception(f"❌ AUTO-INDEX ERROR on message {message.id}: {e}")
