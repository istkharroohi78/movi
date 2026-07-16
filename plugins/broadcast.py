import datetime, time, os, asyncio, logging 
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import MessageTooLong, PeerIdInvalid
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client, filters, enums
from database.users_chats_db import db
from info import ADMINS, GRP_LNK

        
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast(bot, message):
    b_msg = message.reply_to_message
    if not b_msg:
        return await message.reply_text("⚠️ **Error:** Please reply to a message to broadcast it.")

    users = await db.get_all_users()
    sts = await message.reply_text('⏳ **Preparing User Broadcast...**')
    
    start_time = time.time()
    total_users = await db.total_users_count()
    
    if total_users == 0:
        return await sts.edit("❌ **No users found in the database.**")

    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0

    btn = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Search Here", url=GRP_LNK)]
        ]
    )

    async for user in users:
        pti, sh = await broadcast_messages(int(user['id']), b_msg, reply_markup=btn)
        if pti:
            success += 1
        elif pti == False:
            if sh == "Blocked":
                blocked += 1
            elif sh == "Deleted":
                deleted += 1
            elif sh == "Error":
                failed += 1
                
        done += 1
        
        # Update progress bar every 20 users or at the very end
        if done % 20 == 0 or done == total_users:
            percent = (done / total_users) * 100
            filled_blocks = int((done / total_users) * 20)
            bar = '█' * filled_blocks + '░' * (20 - filled_blocks)
            
            progress_text = (
                f"📡 **User Broadcast In Progress**\n\n"
                f"`[{bar}] {percent:.1f}%`\n\n"
                f"**Total Users:** `{total_users}`\n"
                f"**Completed:** `{done}`\n"
                f"**Success:** `{success}`\n"
                f"**Blocked:** `{blocked}`\n"
                f"**Deleted:** `{deleted}`"
            )
            try:
                await sts.edit(progress_text)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass 
                
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.delete()
    await bot.send_message(
        message.chat.id, 
        f"✅ **User Broadcast Completed**\n\n"
        f"⏱ **Time Taken:** `{time_taken}`\n\n"
        f"📊 **Total Users:** `{total_users}`\n"
        f"✅ **Success:** `{success}`\n"
        f"🚫 **Blocked:** `{blocked}`\n"
        f"🗑 **Deleted:** `{deleted}`\n"
        f"❌ **Failed:** `{failed}`"
    )


@Client.on_message(filters.command("clear_junk") & filters.user(ADMINS))
async def remove_junkuser__db(bot, message):
    users = await db.get_all_users()
    b_msg = message 
    sts = await message.reply_text('⏳ **Scanning for junk users...**')   
    
    start_time = time.time()
    total_users = await db.total_users_count()
    
    if total_users == 0:
        return await sts.edit("❌ **No users found in the database.**")
        
    blocked = 0
    deleted = 0
    failed = 0
    done = 0
    
    async for user in users:
        pti, sh = await clear_junk(int(user['id']), b_msg)
        if pti == False:
            if sh == "Blocked":
                blocked += 1
            elif sh == "Deleted":
                deleted += 1
            elif sh == "Error":
                failed += 1
        done += 1
        
        if done % 20 == 0 or done == total_users:
            percent = (done / total_users) * 100
            filled_blocks = int((done / total_users) * 20)
            bar = '█' * filled_blocks + '░' * (20 - filled_blocks)
            
            progress_text = (
                f"🧹 **Clearing Junk Users**\n\n"
                f"`[{bar}] {percent:.1f}%`\n\n"
                f"**Total Users:** `{total_users}`\n"
                f"**Checked:** `{done}`\n"
                f"**Blocked Found:** `{blocked}`\n"
                f"**Deleted Found:** `{deleted}`"
            )
            try:
                await sts.edit(progress_text)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass
                
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.delete()
    await bot.send_message(
        message.chat.id, 
        f"✅ **Junk Clearing Completed**\n\n"
        f"⏱ **Time Taken:** `{time_taken}`\n\n"
        f"📊 **Total Users:** `{total_users}`\n"
        f"✅ **Checked:** `{done}`\n"
        f"🚫 **Removed Blocked:** `{blocked}`\n"
        f"🗑 **Removed Deleted:** `{deleted}`"
    )


@Client.on_message(filters.command("group_broadcast") & filters.user(ADMINS))
async def broadcast_group(bot, message):
    b_msg = message.reply_to_message
    if not b_msg:
        return await message.reply_text("⚠️ **Error:** Please reply to a message to broadcast it to groups.")

    groups = await db.get_all_chats()
    sts = await message.reply_text('⏳ **Preparing Group Broadcast...**')
    
    start_time = time.time()
    total_groups = await db.total_chat_count()
    
    if total_groups == 0:
        return await sts.edit("❌ **No groups found in the database.**")

    done = 0
    failed_reasons = ""
    success = 0
    deleted = 0
    
    async for group in groups:
        chat_id = int(group['id'])
        pti, sh, ex = await broadcast_messages_group(chat_id, b_msg)
        
        if pti:
            success += 1
        else:
            if sh == "deleted":
                deleted += 1 
                failed_reasons += f"ID {chat_id}: {ex}" 
                try:
                    await bot.leave_chat(chat_id)
                except Exception:
                    pass 
                
        done += 1
        
        if done % 20 == 0 or done == total_groups:
            percent = (done / total_groups) * 100
            filled_blocks = int((done / total_groups) * 20)
            bar = '█' * filled_blocks + '░' * (20 - filled_blocks)
            
            progress_text = (
                f"📡 **Group Broadcast In Progress**\n\n"
                f"`[{bar}] {percent:.1f}%`\n\n"
                f"**Total Groups:** `{total_groups}`\n"
                f"**Completed:** `{done}`\n"
                f"**Success:** `{success}`\n"
                f"**Removed:** `{deleted}`"
            )
            try:
                await sts.edit(progress_text)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass 
                
    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts.delete()
    
    final_text = (
        f"✅ **Group Broadcast Completed**\n\n"
        f"⏱ **Time Taken:** `{time_taken}`\n\n"
        f"📊 **Total Groups:** `{total_groups}`\n"
        f"✅ **Success:** `{success}`\n"
        f"❌ **Removed/Failed:** `{deleted}`"
    )
    
    if failed_reasons:
        try:
            await message.reply_text(f"{final_text}\n\n**Failure Reasons (Preview):**\n`{failed_reasons[:1000]}`")
        except MessageTooLong:
            with open('group_reasons.txt', 'w+') as outfile:
                outfile.write(failed_reasons)
            await message.reply_document('group_reasons.txt', caption=final_text)
            os.remove("group_reasons.txt")
    else:
        await message.reply_text(final_text)


@Client.on_message(filters.command(["junk_group", "clear_junk_group"]) & filters.user(ADMINS))
async def junk_clear_group(bot, message):
    groups = await db.get_all_chats()
    b_msg = message
    sts = await message.reply_text('⏳ **Scanning for junk groups...**')
    
    start_time = time.time()
    total_groups = await db.total_chat_count()
    
    if total_groups == 0:
        return await sts.edit("❌ **No groups found in the database.**")
        
    done = 0
    failed_reasons = ""
    deleted = 0
    
    async for group in groups:
        chat_id = int(group['id'])
        pti, sh, ex = await junk_group_helper(chat_id, b_msg)        
        
        if pti == False:
            if sh == "deleted":
                deleted += 1 
                failed_reasons += f"ID {chat_id}: {ex}" 
                try:
                    await bot.leave_chat(chat_id)
                except Exception:
                    pass 
        done += 1
        
        if done % 20 == 0 or done == total_groups:
            percent = (done / total_groups) * 100
            filled_blocks = int((done / total_groups) * 20)
            bar = '█' * filled_blocks + '░' * (20 - filled_blocks)
            
            progress_text = (
                f"🧹 **Clearing Junk Groups**\n\n"
                f"`[{bar}] {percent:.1f}%`\n\n"
                f"**Total Groups:** `{total_groups}`\n"
                f"**Checked:** `{done}`\n"
                f"**Removed:** `{deleted}`"
            )
            try:
                await sts.edit(progress_text)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass
                
    time_taken = datetime.timedelta(seconds=int(time.time()-start_time))
    await sts.delete()
    
    final_text = (
        f"✅ **Group Junk Clearing Completed**\n\n"
        f"⏱ **Time Taken:** `{time_taken}`\n\n"
        f"📊 **Total Groups:** `{total_groups}`\n"
        f"✅ **Checked:** `{done}`\n"
        f"🗑 **Removed:** `{deleted}`"
    )
    
    if failed_reasons:
        try:
            await bot.send_message(message.chat.id, f"{final_text}\n\n**Failure Reasons (Preview):**\n`{failed_reasons[:1000]}`")    
        except MessageTooLong:
            with open('junk_groups.txt', 'w+') as outfile:
                outfile.write(failed_reasons)
            await message.reply_document('junk_groups.txt', caption=final_text)
            os.remove("junk_groups.txt")
    else:
        await bot.send_message(message.chat.id, final_text)


# ================== HELPER FUNCTIONS ==================

async def broadcast_messages_group(chat_id, message):
    try:
        await message.copy(chat_id=chat_id)
        return True, "Success", 'None'
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages_group(chat_id, message)
    except Exception as e:
        await db.delete_chat(int(chat_id))        
        logging.info(f"{chat_id} - Removed from DB (Error: {e})")
        return False, "deleted", f"{e}\n"
    

async def junk_group_helper(chat_id, message):
    try:
        kk = await message.copy(chat_id=chat_id)
        await kk.delete(True)
        return True, "Success", 'None'
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await junk_group_helper(chat_id, message)
    except Exception as e:
        await db.delete_chat(int(chat_id))        
        logging.info(f"{chat_id} - Removed from DB (Error: {e})")
        return False, "deleted", f"{e}\n"
    

async def clear_junk(user_id, message):
    try:
        key = await message.copy(chat_id=user_id)
        await key.delete(True)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await clear_junk(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - Removed from DB, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        logging.info(f"{user_id} - Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception:
        return False, "Error"


async def broadcast_messages(user_id, message, reply_markup=None):
    try:
        await message.copy(chat_id=user_id, reply_markup=reply_markup)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message, reply_markup=reply_markup)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - Removed from DB, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        logging.info(f"{user_id} - Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception:
        return False, "Error"
