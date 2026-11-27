"""Demo content: original sample text for a catalogue that covers every topic tag.

Nothing here is a real book. Each category has a bank of sentences; a book is assembled from its category's bank,
chapter by chapter, so the catalogue has many books of different lengths without copying anyone's work."""

from __future__ import annotations

from dataclasses import dataclass

BANKS: dict[str, list[str]] = {
    "tieu-thuyet": [
        "Cơn gió cuối mùa lùa qua mái hiên, mang theo mùi rơm mới phơi.",
        "Bà ngồi trước hiên nhà, đôi mắt nhìn về phía con đường đất đỏ quen thuộc.",
        "\"Con về rồi đấy à?\" bà hỏi, giọng run run như sợ giấc mơ tan mất.",
        "Tôi đặt chiếc ba lô xuống nền gạch cũ và im lặng rất lâu.",
        "Mười năm xa quê, mọi thứ đổi thay, chỉ có cây gạo đầu làng vẫn đứng đó.",
        "- Bao giờ con đi tiếp? - bà hỏi, tay vẫn đều đặn vuốt tà áo.",
        "Những buổi chiều ở đây trôi chậm như dòng sông lười biếng sau nhà.",
        "Tôi nhận ra mình nhớ tiếng gà gáy hơn bất kỳ âm thanh nào của thành phố.",
        "Bếp lửa chiều nay đỏ rực, hắt lên khuôn mặt hằn dấu thời gian của mẹ.",
        "Có những nỗi nhớ không gọi thành tên, chỉ lặng lẽ lớn lên cùng năm tháng.",
        "\"Ở lại thêm vài hôm nữa nhé,\" mẹ nói và quay đi để giấu đôi mắt đỏ.",
        "Đêm đó tôi nằm nghe mưa rơi trên mái ngói và ngủ một giấc thật sâu.",
    ],
    "trinh-tham": [
        "Chiếc đồng hồ trên tường dừng lại đúng mười một giờ mười lăm phút.",
        "Thám tử Lâm cúi xuống, ngón tay lướt nhẹ trên vết xước gần ổ khóa.",
        "\"Không có dấu hiệu cạy cửa,\" anh nói, \"nghĩa là kẻ đó có chìa khóa.\"",
        "Người quản gia khẽ siết chặt đôi găng tay trắng và tránh ánh mắt của anh.",
        "Trên bàn, ly trà vẫn còn ấm, chứng tỏ căn phòng mới có người rời đi.",
        "- Ông đã ở đâu vào đêm qua? - Lâm hỏi, giọng đều đều như đang đọc báo.",
        "Một sợi chỉ xanh mắc vào gai hoa hồng dưới cửa sổ đã kể cho anh nhiều điều.",
        "Mọi manh mối dường như chỉ về một hướng, nhưng anh vẫn thấy có gì đó sai sai.",
        "Cơn mưa ngoài kia xóa sạch dấu chân, chỉ để lại câu hỏi chưa có lời đáp.",
        "Lâm lật lại cuốn sổ ghi chép và gạch chân tên người cuối cùng gặp nạn nhân.",
        "\"Sự thật luôn nằm ở chi tiết nhỏ nhất,\" anh lẩm bẩm rồi mỉm cười.",
        "Khi ánh đèn bật sáng, kẻ giấu mặt cuối cùng cũng không còn chỗ để trốn.",
    ],
    "khoa-hoc": [
        "Ánh sáng mặt trời thực chất là sự pha trộn của nhiều màu sắc khác nhau.",
        "Khi đi qua khí quyển, ánh sáng xanh bị phân tán mạnh hơn các màu còn lại.",
        "Đó là lý do ban ngày bầu trời mang màu xanh dịu mắt mà chúng ta quen nhìn.",
        "Mỗi giọt nước trong đại dương đều từng bay lên thành mây rồi rơi xuống thành mưa.",
        "Nhà khoa học gọi hiện tượng này là vòng tuần hoàn của nước trên Trái Đất.",
        "Chỉ một phần rất nhỏ lượng nước trên hành tinh là nước ngọt có thể dùng được.",
        "Các tế bào trong cơ thể chúng ta liên tục chết đi và được thay thế mới.",
        "Thí nghiệm đơn giản nhất thường mở ra những câu hỏi lớn nhất của khoa học.",
        "Kính hiển vi cho phép ta nhìn thấy một thế giới sống động trong giọt nước ao.",
        "Mọi phát minh vĩ đại đều bắt đầu từ sự tò mò của một người dám đặt câu hỏi.",
        "Trọng lực giữ chúng ta trên mặt đất và giữ Mặt Trăng quay quanh Trái Đất.",
        "Hiểu được quy luật của tự nhiên giúp con người sống hài hòa hơn với nó.",
    ],
    "lich-su": [
        "Con đường cổ này từng là tuyến giao thương nhộn nhịp bậc nhất của vùng đất.",
        "Các thương nhân chở muối, vải và gốm sứ đi qua đây từ hàng trăm năm trước.",
        "Những phiến đá lát đường còn hằn dấu bánh xe của những đoàn xe thồ xưa.",
        "Theo ghi chép của người xưa, một trạm nghỉ chân được dựng cứ mỗi ngày đường.",
        "Triều đại ấy trị vì trong bối cảnh đất nước vừa trải qua nhiều biến động.",
        "Các nhà sử học dựa vào bia ký và thư tịch cổ để dựng lại bức tranh quá khứ.",
        "Mỗi di tích còn lại là một trang sách mở ra cho thế hệ sau đọc và suy ngẫm.",
        "Cuộc kháng chiến kéo dài nhiều năm đã tôi luyện ý chí của cả một dân tộc.",
        "Làng nghề truyền thống giữ lại cho chúng ta những bí quyết có từ nhiều thế kỷ.",
        "Hiểu lịch sử không phải để nhớ ngày tháng mà để hiểu vì sao ta là ta hôm nay.",
        "Qua thời gian, tên gọi của con đường đã đổi thay nhưng ký ức vẫn còn nguyên.",
        "Người dân địa phương vẫn kể cho con cháu nghe những câu chuyện về thuở ấy.",
    ],
    "ky-nang-song": [
        "Mười phút đầu tiên của buổi sáng quyết định phần lớn tâm trạng cả ngày.",
        "Hãy bắt đầu bằng một việc nhỏ, đơn giản và chắc chắn làm được mỗi ngày.",
        "Thói quen tốt không đến từ ý chí mạnh mà đến từ môi trường được sắp đặt khéo.",
        "Khi từ chối một việc, hãy nói rõ ràng, lịch sự và không cần giải thích quá dài.",
        "Ghi lại ba điều biết ơn mỗi tối giúp đầu óc quen nhìn vào điều tích cực.",
        "Quản lý thời gian thực chất là quản lý sự chú ý của chính mình.",
        "Đừng so sánh phần đầu của mình với phần cuối trong câu chuyện của người khác.",
        "Nghỉ ngơi đúng lúc không phải lười biếng mà là một phần của làm việc hiệu quả.",
        "Một mục tiêu rõ ràng được chia nhỏ sẽ bớt đáng sợ và dễ bắt tay vào làm.",
        "Lắng nghe trọn vẹn là món quà quý giá nhất bạn có thể dành cho người đối diện.",
        "Sai lầm là người thầy nghiêm khắc nhưng dạy cho ta những bài học nhớ lâu nhất.",
        "Kiên trì mỗi ngày một chút sẽ đưa bạn đi xa hơn nỗ lực dồn dập trong một tuần.",
    ],
    "tam-ly": [
        "Lo lắng là phản ứng tự nhiên của cơ thể khi nó cảm thấy sắp có điều gì đó xảy ra.",
        "Hít thở chậm và sâu giúp hệ thần kinh dần dịu lại sau một ngày căng thẳng.",
        "Gọi tên cảm xúc của mình là bước đầu tiên để hiểu và làm chủ nó.",
        "Không ai hoàn hảo, và việc chấp nhận điều đó giúp ta nhẹ nhõm hơn rất nhiều.",
        "Những suy nghĩ tiêu cực lặp đi lặp lại thường không phản ánh toàn bộ sự thật.",
        "Chia sẻ với một người đáng tin có thể làm gánh nặng trong lòng vơi đi đáng kể.",
        "Giấc ngủ đủ và vận động nhẹ nhàng là nền tảng của một tinh thần khỏe mạnh.",
        "Cảm giác cô đơn không có nghĩa là bạn thiếu giá trị, chỉ là bạn đang cần kết nối.",
        "Học cách tự nói với mình bằng giọng dịu dàng như với một người bạn thân.",
        "Áp lực trở thành động lực khi ta biết chia nhỏ và đón nhận nó từng chút một.",
        "Đôi khi điều ta cần không phải lời khuyên mà là một người chịu ngồi nghe.",
        "Chăm sóc tâm trí cũng quan trọng như chăm sóc cơ thể mỗi ngày.",
    ],
    "triet-hoc": [
        "Người đi tìm chiếc bóng của mình rồi nhận ra bóng chỉ có khi ta đứng dưới ánh sáng.",
        "Hạnh phúc có phải là đích đến hay chỉ là cách ta bước đi trên đường?",
        "Con người sống giữa hai bờ: điều đã qua không lấy lại và điều chưa tới.",
        "Khi hiểu rằng mọi thứ đều đổi thay, ta bớt đau đớn trước sự mất mát.",
        "Câu hỏi hay đôi khi có giá trị hơn một trăm câu trả lời vội vàng.",
        "Tự do thực sự bắt đầu khi ta dám chịu trách nhiệm về lựa chọn của mình.",
        "Người khôn ngoan biết mình biết ít, và vì thế không ngừng học hỏi.",
        "Cái đẹp nằm trong mắt người nhìn, nhưng nhìn thế nào lại do tâm ta quyết định.",
        "Giữa ồn ào của cuộc sống, sự tĩnh lặng là một nơi trú ẩn hiếm có.",
        "Thời gian không phải thứ ta có, mà là thứ ta đang sống trong đó.",
        "Có những chân lý chỉ hiện ra khi ta ngừng cố gắng nắm giữ chúng.",
        "Sống tử tế có lẽ là câu trả lời giản dị nhất cho những câu hỏi lớn lao nhất.",
    ],
    "cong-nghe": [
        "Trí tuệ nhân tạo học từ rất nhiều ví dụ thay vì được lập trình từng bước.",
        "Một mô hình ngôn ngữ dự đoán từ tiếp theo dựa trên những gì nó đã thấy trước đó.",
        "Dữ liệu tốt quan trọng không kém thuật toán tốt khi huấn luyện một hệ thống thông minh.",
        "Mỗi khi bạn mở một trang web, máy tính của bạn gửi yêu cầu đến một máy chủ ở xa.",
        "Địa chỉ trên Internet giống như địa chỉ nhà giúp dữ liệu tìm đúng nơi cần đến.",
        "Mật khẩu mạnh và xác thực hai lớp là hàng rào đơn giản nhưng rất hiệu quả.",
        "Điện toán đám mây cho phép thuê sức mạnh máy tính khi cần thay vì mua sẵn.",
        "Phần mềm mã nguồn mở được cả cộng đồng cùng đọc, sửa và cải thiện mỗi ngày.",
        "Máy học không có phép màu; nó chỉ là toán học áp dụng trên lượng dữ liệu rất lớn.",
        "Khi dùng công nghệ, hãy luôn tự hỏi dữ liệu của mình đang được dùng vào việc gì.",
        "Những thiết bị nhỏ trong nhà ngày càng kết nối với nhau thành mạng lưới thông minh.",
        "Học lập trình giúp ta hiểu thế giới số thay vì chỉ là người dùng của nó.",
    ],
    "kinh-te": [
        "Tiền không biết nói, nhưng cách ta tiêu nó kể rất nhiều về điều ta coi trọng.",
        "Lạm phát làm cùng một số tiền mua được ít hàng hóa hơn theo thời gian.",
        "Tiết kiệm đều đặn mỗi tháng quan trọng hơn một khoản lớn gửi vào chỉ một lần.",
        "Lãi kép là sức mạnh thầm lặng biến những khoản nhỏ thành tài sản đáng kể.",
        "Trước khi đầu tư hãy hiểu rõ mình đang mua cái gì và vì sao nó có giá trị.",
        "Quỹ dự phòng giúp ta bình tĩnh hơn khi cuộc sống bất ngờ gửi đến một hóa đơn lớn.",
        "Cung và cầu quyết định giá cả trên thị trường, từ quả cam đến căn nhà.",
        "Chi phí cơ hội nhắc rằng chọn việc này nghĩa là từ bỏ việc khác.",
        "Nợ không phải lúc nào cũng xấu, nhưng nợ tiêu dùng lãi cao thì rất nguy hiểm.",
        "Một ngân sách đơn giản ghi rõ thu và chi giúp bạn thấy tiền đang đi đâu.",
        "Đa dạng hóa là cách giảm rủi ro mà không cần đoán trước tương lai.",
        "Hiểu biết tài chính là kỹ năng sống mà ai cũng nên học càng sớm càng tốt.",
    ],
    "tinh-cam": [
        "Lá thư đầu tiên của anh đến vào một chiều thu, thơm mùi giấy mới và nắng nhạt.",
        "Em giữ nó trong ngăn kéo, thỉnh thoảng lại mở ra đọc như đọc một bài thơ.",
        "\"Anh nhớ em,\" dòng cuối viết, nét chữ nghiêng nghiêng và vội vã.",
        "Chúng tôi gặp nhau giữa mưa, chung một chiếc ô nhỏ và những câu chuyện dài.",
        "Có những người đến trong đời ta chỉ để dạy ta cách yêu thương chân thành.",
        "- Em có đợi anh không? - anh hỏi và nắm lấy tay em thật chặt.",
        "Mùa thu năm ấy lá vàng rơi đầy trên vỉa hè, và tim em cũng đầy những điều chưa nói.",
        "Tình yêu không ồn ào, nó chỉ lặng lẽ ở lại trong những điều rất nhỏ.",
        "Anh pha cho em ly cà phê đúng vị mà em thích, không cần hỏi thêm.",
        "Xa nhau một chặng đường, chúng tôi mới hiểu mình quý nhau đến nhường nào.",
        "\"Đừng sợ,\" em thì thầm, \"có em ở đây rồi.\"",
        "Hạnh phúc đôi khi chỉ là cùng nhau ngồi nhìn hoàng hôn buông xuống thật chậm.",
    ],
    "kinh-di": [
        "Hành lang tầng ba tối hơn bình thường, và ánh đèn cuối dãy cứ chập chờn.",
        "Tôi chắc chắn mình đã khóa cửa căn phòng cuối cùng từ chiều hôm qua.",
        "Một tiếng gõ khe khẽ vang lên từ bên trong, đều đặn như nhịp tim.",
        "\"Có ai trong đó không?\" tôi hỏi, giọng nghẹn lại nơi cổ họng.",
        "Không có tiếng trả lời, chỉ có làn không khí lạnh buốt lùa qua khe cửa.",
        "Trên sàn gỗ xuất hiện những dấu chân ướt, kéo dài từ cửa đến chiếc gương cũ.",
        "- Anh có nghe thấy không? - cô thì thào và níu chặt tay áo tôi.",
        "Chiếc gương phản chiếu căn phòng, nhưng trong đó có thêm một bóng người nữa.",
        "Tôi lùi dần ra phía sau, tim đập mạnh đến mức nghe rõ trong tai.",
        "Đèn vụt tắt, và trong bóng tối ai đó khe khẽ gọi tên tôi.",
        "Sáng hôm sau, căn phòng trống không, chỉ còn chiếc gương phủ một lớp bụi mỏng.",
        "Từ đó không ai dám đi ngang hành lang ấy vào ban đêm nữa.",
    ],
    "phieu-luu": [
        "Con thuyền nhỏ rẽ sóng, hướng về hòn đảo chưa từng được ghi trên bản đồ.",
        "Thuyền trưởng giương ống nhòm, đôi mắt sáng lên dưới vành mũ sờn cũ.",
        "\"Đất liền!\" cậu bé gác buồm reo lên, giọng vỡ ra vì phấn khích.",
        "Bãi cát trắng trải dài, phía sau là rừng cọ rì rào trong gió biển.",
        "Họ men theo dòng suối nhỏ, nơi những viên đá lấp lánh như rắc bụi sao.",
        "- Bản đồ chỉ đến đây thôi, - cô gái nói, - phần còn lại phải tự tìm.",
        "Trong hang động tối, ánh đuốc lung linh soi lên những bức vẽ cổ xưa.",
        "Tiếng thác đổ vang vọng, báo hiệu họ đã gần tới kho báu trong truyền thuyết.",
        "Mỗi bước đi trên đảo đều mở ra một điều kỳ diệu hoặc một thử thách mới.",
        "Chiếc rương cũ kỹ mở ra, bên trong không phải vàng mà là một cuốn nhật ký.",
        "Họ nhận ra kho báu thật sự là những ngày cùng nhau chinh phục biển cả.",
        "Khi mặt trời lặn, con thuyền quay về, mang theo câu chuyện cho cả làng nghe.",
    ],
    "thieu-nhi": [
        "Ngày xửa ngày xưa, có một chú thỏ trắng sống bên bờ suối nhỏ.",
        "Đêm nào thỏ cũng ngước nhìn mặt trăng tròn vành vạnh và thấy thật đẹp.",
        "\"Mình muốn chạm vào mặt trăng,\" thỏ nói với bạn sóc nhỏ.",
        "Sóc cười khúc khích: \"Mặt trăng ở xa lắm, cậu phải đi qua cả khu rừng đấy.\"",
        "Thế là thỏ lên đường, đôi tai dài vẫy vẫy theo từng bước nhảy.",
        "Trên đường đi, thỏ gặp chú cú mèo thông thái đang ngồi trên cành sồi.",
        "- Cháu đi đâu muộn thế? - cú mèo hỏi bằng giọng trầm ấm.",
        "Mèo con lười biếng cuộn tròn trong chiếc giỏ, ngáp một cái thật dài.",
        "Các bạn nhỏ cùng nhau giúp thỏ bắc một chiếc thang bằng những chiếc lá lớn.",
        "Thỏ nhận ra mặt trăng cũng soi bóng xuống mặt hồ ngay dưới chân mình.",
        "Từ đó, mỗi đêm thỏ ngồi bên hồ ngắm trăng cùng những người bạn thân.",
        "Và các bạn nhỏ ngủ ngon lành với nụ cười trên môi.",
    ],
    "truyen-ngan": [
        "Câu chuyện thứ nhất bắt đầu bằng một chiếc ghế trống ở cuối quán cà phê.",
        "Ông chủ quán nói rằng chiếc ghế ấy dành cho người sẽ không bao giờ quay lại.",
        "Mỗi chiều có một người đàn ông đến, gọi hai tách trà và chỉ uống một.",
        "\"Bà ấy thích trà nóng,\" ông giải thích khi thấy tôi tò mò nhìn.",
        "Câu chuyện thứ hai kể về một chiếc ô để quên trên chuyến xe buýt muộn.",
        "Chủ nhân nó tìm lại sau ba tuần và bất ngờ gặp người đã giữ hộ chiếc ô.",
        "Câu chuyện cuối là về một bức thư gửi nhầm địa chỉ suốt mười năm.",
        "Người nhận không biết người gửi, nhưng đã trả lời từng lá thư một.",
        "Đôi khi một sự nhầm lẫn nhỏ lại thành khởi đầu của một tình bạn dài lâu.",
        "- Có lẽ số phận thích đùa, - tôi nói, và cả hai cùng bật cười.",
        "Quán đóng cửa muộn hơn mọi ngày, vì hôm đó ai cũng muốn kể thêm một chuyện nữa.",
        "Ra về, tôi thấy phố đêm bỗng dịu dàng hơn thường lệ.",
    ],
}


@dataclass(frozen=True)
class DemoBook:
    title: str
    author: str
    category: str  # slug
    chapters: int
    sentences: int  # per chapter


BOOKS: tuple[DemoBook, ...] = (
    DemoBook("Mùa Hoa Gạo Cuối Làng", "Lê Thu Hạnh", "tieu-thuyet", 5, 10),
    DemoBook("Con Đường Về Nhà", "Phạm Quang Tín", "tieu-thuyet", 24, 16),
    DemoBook("Vụ Án Chiếc Đồng Hồ Ngưng Chạy", "Đỗ Minh Khôi", "trinh-tham", 6, 12),
    DemoBook("Bóng Người Dưới Mưa", "Đỗ Minh Khôi", "trinh-tham", 4, 10),
    DemoBook("Vì Sao Bầu Trời Có Màu Xanh", "Nguyễn Hải Yến", "khoa-hoc", 5, 10),
    DemoBook("Hành Trình Của Một Giọt Nước", "Nguyễn Hải Yến", "khoa-hoc", 3, 8),
    DemoBook("Chuyện Một Con Đường Cổ", "Trần Văn Lộc", "lich-su", 6, 12),
    DemoBook("Mười Phút Mỗi Sáng", "Vũ Bảo Anh", "ky-nang-song", 4, 10),
    DemoBook("Học Cách Nói Không", "Vũ Bảo Anh", "ky-nang-song", 3, 8),
    DemoBook("Khi Ta Lo Lắng", "Hoàng Mai Chi", "tam-ly", 5, 10),
    DemoBook("Người Đi Tìm Chiếc Bóng", "Bùi An Nhiên", "triet-hoc", 4, 10),
    DemoBook("Trí Tuệ Nhân Tạo Cho Mọi Nhà", "Ngô Đức Thịnh", "cong-nghe", 16, 14),
    DemoBook("Internet Hoạt Động Thế Nào", "Ngô Đức Thịnh", "cong-nghe", 3, 8),
    DemoBook("Tiền Không Biết Nói", "Đặng Thùy Linh", "kinh-te", 5, 10),
    DemoBook("Thư Gửi Mùa Thu", "Lê Thu Hạnh", "tinh-cam", 4, 10),
    DemoBook("Hai Chiếc Ô Một Chiều Mưa", "Lê Thu Hạnh", "tinh-cam", 3, 8),
    DemoBook("Căn Phòng Cuối Hành Lang", "Trịnh Nhật Vũ", "kinh-di", 4, 10),
    DemoBook("Hòn Đảo Không Có Trên Bản Đồ", "Phạm Quang Tín", "phieu-luu", 20, 16),
    DemoBook("Chú Thỏ Tìm Mặt Trăng", "Mộc Miên", "thieu-nhi", 2, 8),
    DemoBook("Bạn Mèo Lười Biếng", "Mộc Miên", "thieu-nhi", 2, 6),
    DemoBook("Ba Câu Chuyện Nhỏ", "Ngọc Lan", "truyen-ngan", 3, 8),
    DemoBook("Mật Mã Trong Phòng Kín", "Đỗ Minh Khôi", "trinh-tham", 8, 12),
    DemoBook("Tiếng Thì Thầm Trong Giếng Cũ", "Trịnh Nhật Vũ", "kinh-di", 5, 10),
    DemoBook("Kho Báu Dưới Đáy Hồ", "Phạm Quang Tín", "phieu-luu", 6, 12),
    DemoBook("Vũ Trụ Trong Lòng Bàn Tay", "Nguyễn Hải Yến", "khoa-hoc", 8, 12),
    DemoBook("Lập Trình Từ Con Số Không", "Ngô Đức Thịnh", "cong-nghe", 10, 12),
    DemoBook("Đầu Tư Cho Người Mới Bắt Đầu", "Đặng Thùy Linh", "kinh-te", 6, 12),
    DemoBook("Thói Quen Nhỏ Thay Đổi Lớn", "Vũ Bảo Anh", "ky-nang-song", 5, 10),
)

# Reading history to give the two demo accounts different tastes: (title, status, completion %, minutes, favourite)
HISTORY: dict[str, list[tuple[str, str, float, int, bool]]] = {
    "khanhhoa36": [  # likes suspense
        ("Vụ Án Chiếc Đồng Hồ Ngưng Chạy", "completed", 100.0, 22, True),
        ("Căn Phòng Cuối Hành Lang", "reading", 60.0, 14, False),
        ("Hòn Đảo Không Có Trên Bản Đồ", "reading", 25.0, 18, False),
    ],
    "xuanhai18": [  # likes learning
        ("Trí Tuệ Nhân Tạo Cho Mọi Nhà", "completed", 100.0, 40, False),
        ("Internet Hoạt Động Thế Nào", "completed", 100.0, 12, True),
        ("Tiền Không Biết Nói", "reading", 70.0, 16, False),
    ],
}


def book_text(book: DemoBook) -> str:
    """The whole text of a demo book: a title line, then chapters built from the category's sentence bank."""
    bank = BANKS[book.category]
    seed = sum(ord(c) for c in book.title)
    lines = [f"{book.title}", "(Nội dung mẫu phục vụ trình diễn hệ thống.)", ""]
    for chapter in range(1, book.chapters + 1):
        lines.append(f"Chương {chapter}")
        lines.append("")
        start = (seed + chapter * 5) % len(bank)
        sentences = [bank[(start + i * 7) % len(bank)] for i in range(book.sentences)]
        for i in range(0, len(sentences), 4):
            lines.append(" ".join(sentences[i:i + 4]))
            lines.append("")
    return "\n".join(lines)
