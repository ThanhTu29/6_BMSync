from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

def chatbot_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message', '')
        # Tích hợp GenMini và agent_sql ở đây
        # Ví dụ mô phỏng: nếu câu hỏi chứa 'số lượng', trả về số mẫu từ database
        # Thực tế: cần gọi GenMini để phân tích ý định, sinh SQL, thực thi và trả kết quả
        if 'số lượng' in user_message:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM users_profile')
                row = cursor.fetchone()
            bot_response = f"Số lượng tài khoản: {row[0]}"
        else:
            bot_response = "Tôi chưa hiểu câu hỏi. Vui lòng hỏi lại hoặc cụ thể hơn."
        return JsonResponse({'response': bot_response})
    return render(request, 'chatbot/chatbot.html')
