# Macro Vision v8 — xác nhận kích hoạt và xét lần lượt

Đây là bản sửa tiếp trên giao diện Tkinter của v8, không phải giao diện v9. Mở file script cũ bằng **Mở script**. Script không tự mở lúc khởi động.

Mode Một lần không giới hạn thời gian tìm/xét. Ô thời gian được giữ riêng cho mode Lặp lại; lỗi chồng nhãn checkbox xác nhận trước đây đã được sửa.

## Chọn phím bằng cách bấm trực tiếp

Chọn thao tác loại **Phím**, đặt con trỏ vào ô **Bấm phím để chọn**, sau đó bấm các phím trên bàn phím. App ghi tên từng phím và tự ngăn cách bằng dấu cách. Ví dụ bấm lần lượt `S`, `H`, `I`, `F`, `T` cho `S H I F T`; bấm phím Shift thật cho `Shift`. Bấm nút cách ghi `Space`.

Mỗi phím trong một ô là một **tổ hợp**: app gửi lần lượt các lệnh nhấn rất nhanh, giữ các phím cùng lúc theo thời gian giữ của thao tác, rồi nhả theo thứ tự ngược lại; không thể bảo đảm các lệnh đến chính xác cùng thời điểm. Lặp thao tác sẽ nhấn/nhả lại cả tổ hợp. Mỗi phím chỉ xuất hiện một lần trong tổ hợp. Nếu thao tác cùng số thứ tự chia sẻ một phím, app báo lỗi trước khi chạy để tránh nhả lẫn nhau.

**Backspace** không dùng làm thao tác: nó xóa phím trước con trỏ (hoặc phím đang chứa con trỏ); chọn vùng chữ rồi Backspace để xóa các phím trong vùng. Nhấp chuột để đặt con trỏ. **F6, F7, F8** không ghi vào ô và **không điều khiển app khi ô đó đang được chọn**. Để dừng lúc đang sửa ô, bấm nút Dừng hoặc rời ô rồi nhấn F8. Nếu ô trống, hãy nhập ít nhất một phím trước khi chạy/chuyển mục.

Hỗ trợ các phím chữ/số, Shift/Ctrl/Alt, Space, Esc, Enter, Tab, mũi tên, Home/End, Insert/Delete, PageUp/PageDown, F1–F24 trừ F6–F8, các phím numpad và một số phím dấu/Windows thông dụng. Một số phím hệ thống, phím đa phương tiện, tổ hợp được Windows giữ riêng hoặc layout đặc biệt có thể không được chuyển đến ứng dụng; không hứa nhận được mọi phím/bàn phím. Phím dấu được lưu theo mã phím vật lý Windows, nên ký tự thực tế phụ thuộc layout. Chỉ ghi nhận thao tác khi app có focus; cách thử an toàn là dùng Notepad.

Script cũ vẫn tương thích: giá trị cũ `SHIFT` tiếp tục là một phím Shift, không tự chuyển thành `S H I F T`. Các thay đổi trong lúc chạy chỉ áp dụng vào lần chạy sau; bấm **Lưu script** để giữ lại.

## Kéo thả sắp xếp cấu trúc

Tính năng dùng được ở cả hai mode. Nhấn giữ vào **tên** mục trong cây, kéo đến vị trí muốn đặt rồi nhả; đường xanh cho biết vị trí thả. Thả ở nửa trên/dưới mục cùng loại để đặt trước/sau. Có thể đưa chuột gần mép trên/dưới cây khi kéo để cuộn; nhấn Esc để hủy. Nút tam giác vẫn dùng để thu gọn/mở rộng.

- **Luồng**: kéo trước/sau luồng khác; toàn bộ điều kiện và thao tác bên trong đi theo.
- **Điều kiện**: kéo trước/sau điều kiện khác (kể cả ở luồng khác), hoặc thả lên tên luồng để đưa vào cuối luồng đó. Các thao tác bên trong đi theo.
- **Thao tác**: kéo trước/sau thao tác khác (kể cả trong điều kiện khác), hoặc thả lên tên điều kiện để đưa vào cuối điều kiện đó. Mọi thiết lập của thao tác, kể cả **Số thứ tự**, được giữ nguyên.

**Quan trọng:** điều kiện và luồng chạy/xét theo thứ tự trên cây; thao tác vẫn chạy theo **Số thứ tự** chứ không theo vị trí hiển thị trên cây. Thao tác cùng số vẫn tạo một nhóm chạy gần đồng thời; kéo sang điều kiện khác có thể đưa thao tác vào nhóm cùng số đang có ở đó. Tự sửa Số thứ tự nếu cần thay đổi trình tự. Nếu nhóm có phím trùng, nhiều thao tác chuột, hoặc nhóm đầu không hợp lệ khi bật xác nhận, app sẽ báo lỗi khi bắt đầu; hãy tự chỉnh trước khi chạy. Tương tự, luồng không có điều kiện hoặc điều kiện không có thao tác không thể chạy.

Kéo thả chỉ sửa script đang mở trong bộ nhớ; bấm **Lưu script** để giữ thay đổi. Nếu đang chạy, thứ tự mới chỉ áp dụng từ lần chạy tiếp theo, không đổi chuỗi hiện tại.

## Mode của toàn bộ script

Ở cạnh **Cấu trúc script**, chọn **Mode script: Lặp lại / Một lần**. Đây là mode của toàn bộ script, khác trường **Cách kích hoạt** của từng điều kiện.

- **Lặp lại**: dùng nguyên bộ chạy cũ và các giá trị riêng của từng điều kiện. Xét luồng, điều kiện từ trên xuống; sau chuỗi xét tiếp điều kiện kế tiếp, hết lượt mới quay lại đầu. Chuyển sang mode Một lần rồi chuyển lại không làm mất cấu hình.
- **Một lần**: bộ chạy riêng. Xét luồng và từng điều kiện theo thứ tự từ trên xuống. Mỗi điều kiện phải đạt, được kích hoạt và chạy **xong toàn bộ chuỗi một lần** trước khi chuyển sang điều kiện tiếp theo. App tìm và xét điều kiện **không giới hạn thời gian**. Nếu ảnh mất khớp trong lúc chờ ổn định hoặc không đạt khi kiểm tra lại, bộ đếm ổn định đặt lại và app tiếp tục chờ chính điều kiện đó, không chuyển tiếp. Sau khi tất cả điều kiện trong luồng chạy xong mới sang luồng tiếp theo; sau điều kiện cuối của luồng cuối, script tự dừng. Không chạy lại điều kiện đã hoàn thành và không có hàng đợi.
- Có thể chờ ở một điều kiện vô thời hạn nếu nó không đạt; F8 dừng. Nếu mất focus trong khi đang tìm/xét thì chờ lấy lại focus và đo lại điều kiện đang xét. Nếu mất focus trong khi đang thực hiện chuỗi, mode Một lần **dừng toàn bộ** để tránh tự chạy lại thao tác đã làm dở; F6 bắt đầu lại từ luồng đầu. F7 tạm dừng/tiếp tục, F8 dừng và nhả đầu vào đang giữ.
- Trong mode Một lần, các trường điều kiện **Thời gian tìm / xét ổn định**, **Không đạt ổn định để chạy lại**, **Cách kích hoạt**, **Nghỉ sau chuỗi**, **Số lần tối đa**, **Không giới hạn** được ẩn và không có tác dụng. Giá trị được giữ nguyên trong script. Tất cả các trường nhận diện, **Ổn định ít nhất**, **Xác nhận đã kích hoạt** và cấu hình thao tác vẫn có tác dụng. Nếu xác nhận không thấy dấu hiệu thay đổi, chuỗi có thể chờ vô hạn như mô tả bên dưới. Nếu tăng Ổn định ít nhất vượt quá thời gian tìm/xét đã lưu, khi chuyển về Lặp lại cần tăng thời gian tìm/xét cho hợp lệ.
- Mode được lưu **trong script** khi bấm Lưu script. Script cũ không chứa mode và script mới mặc định **Lặp lại**. Đổi mode hoặc chỉnh cấu hình trong khi đang chạy chỉ áp dụng vào lần F6 tiếp theo, không thay đổi lượt chạy hiện tại. Nhớ lưu script sau khi chỉnh.

Các phần bên dưới mô tả hành vi cũ của mode **Lặp lại**, trừ khi ghi rõ khác. Riêng mode Một lần không có hạn tìm/xét nên không ghi dòng “Chưa kích hoạt” do hết hạn; trạng thái chờ vẫn hiện trên giao diện.

## Tùy chọn mới của điều kiện

- **Không giới hạn** cạnh **Số lần tối đa**: khi tích, không áp dụng giới hạn số lần kích hoạt (ô số lần được vô hiệu hóa, giá trị cũ được giữ). Cách kích hoạt **Một lần/Lặp**, thời gian nghỉ và điều kiện mở lại vẫn áp dụng như trước; tích này không tự chuyển sang chế độ Lặp.
- **Xác nhận đã kích hoạt**: sau khi điều kiện đạt và kiểm tra lại, app nhấn và nhả thao tác có số thứ tự nhỏ nhất, sau đó liên tục theo dõi chính vùng ảnh và mask của điều kiện. Nếu tín hiệu chưa đổi, khoảng **150 ms sau nhả**, kiểm tra lại rồi nhấn/nhả thao tác đó lần nữa. Khi quan sát thấy điều kiện **không còn đạt ít nhất một trong ba ngưỡng ảnh, màu hoặc sáng**, app coi đã xác nhận và chạy các nhóm còn lại theo thứ tự; không chạy lại thao tác đầu trong phần còn lại. Một lần không đạt là đủ, không đợi ổn định. Vì ảnh được lấy mẫu rời rạc, thay đổi thoáng qua có thể bị bỏ lỡ; thay đổi ánh sáng/nền cũng có thể làm xác nhận sớm. Chỉnh mask và ngưỡng phù hợp.
- Trong chế độ xác nhận, mỗi lần thử dùng thời gian giữ và cấu hình phím/chuột của thao tác đầu nhưng **bỏ qua số lần lặp và khoảng nghỉ giữa các lần** của riêng thao tác đó: lặp được quyết định bởi tín hiệu và khoảng 150 ms. **Chờ sau thao tác** của thao tác đầu được áp dụng một lần sau khi đã xác nhận, trước nhóm tiếp theo. Các thao tác sau vẫn giữ cấu hình bình thường.
- Khi bật xác nhận, nhóm số thứ tự nhỏ nhất chỉ được có **một thao tác**; nếu có nhiều thao tác cùng số đầu tiên, app báo lỗi trước khi chạy để không tự thay đổi ý nghĩa đồng thời. Tắt xác nhận thì nhóm đồng số hoạt động như cũ.
- Xác nhận không có timeout: nếu dấu hiệu không đổi, app cứ lặp thao tác đầu và **không xét điều kiện khác**. F7 tạm dừng/tiếp tục, F8 dừng; mất focus ngắt chuỗi. Mỗi lần nhấn và nhả được ghi log kèm số lần xác nhận. App chỉ quan sát màn hình, không chứng minh trò chơi đã xử lý thao tác.
- Script cũ mặc định không tích hai tùy chọn; chỉnh các tùy chọn vẫn phải **Lưu script** như thông thường. Giá trị hợp lệ được nhớ làm mặc định cho điều kiện mới.

## Độ giống màu riêng

Mỗi điều kiện có ô **Độ giống màu tối thiểu (0–1)**. App so từng pixel trong mask với đúng pixel tương ứng của ảnh mẫu theo ba kênh B/G/R. Với từng pixel, lấy độ lệch tuyệt đối lớn nhất trong ba kênh, sau đó lấy trung bình trên toàn bộ pixel được chọn; điểm màu là `1 - sai lệch trung bình / 255`, giới hạn 0–1. Điểm 1 là màu các pixel khớp chính xác; 0 là sai lệch tối đa theo phép đo này. Các điểm nằm ngoài mask không được tính.

Đây là phép so **màu tuyệt đối và bị ảnh hưởng bởi sáng/tối**, không phải nhận diện tên màu hay phép đo theo sắc độ bất biến. Hiệu ứng ánh sáng, hoạt ảnh, nền lọt vào mask hoặc lệch vị trí có thể làm thay đổi điểm. Chẳng hạn đỏ `(255,0,0)` so với đỏ tối `(155,0,0)` có điểm màu khoảng **0,608**. Ngưỡng 0,8 sẽ loại ví dụ này, nhưng không có ngưỡng chung phù hợp mọi trạng thái game.

Điều kiện phải đồng thời đạt độ giống ảnh cũ, ngưỡng màu mới và độ sáng tối thiểu. So màu là phép lọc bổ sung; điểm giống ảnh cũ vẫn tính theo BGR, không bị thay thế. Ngưỡng mặc định cho script cũ và điều kiện mới là **0** (không lọc theo màu, vẫn hiển thị điểm). Chỉnh ô cho từng điều kiện rồi bấm **Lưu script**; giá trị hợp lệ mới cũng được ghi nhớ khi tạo điều kiện tiếp theo. Giá trị hoặc ngưỡng là số thực từ 0 tới 1, không phải mã màu RGB.

Log **Kích hoạt**, **Chưa kích hoạt**, **Bỏ qua** và trạng thái theo dõi có thêm điểm màu. Ví dụ `Độ giống màu: 0.6078/0.8000` cho thấy điểm đo được thấp hơn ngưỡng đã đặt. Ngoài bước xác nhận tùy chọn, bản này không ghi log nhận diện điều kiện trong lúc chạy chuỗi, và vẫn giữ quy định chỉ ghi log chưa kích hoạt sau lần kích hoạt đầu tiên, ngừng sau một lượt không có kích hoạt; bật chẩn đoán chi tiết nếu cần thêm lý do. Chỉnh ngưỡng nên dựa trên nhiều mẫu ở cả trạng thái cần chạy và không nên chạy; ngưỡng cao có thể bỏ sót.

## Cơ chế tìm hình và xét ổn định — không có hàng đợi điều kiện

App xét theo thứ tự luồng, điều kiện từ trên xuống. Với mỗi điều kiện được phép chạy, ô **Thời gian tìm / xét ổn định (ms)** quy định cùng một giới hạn cho **mỗi trong hai giai đoạn**, không phải tổng của cả hai:

1. Khi đến lượt, bắt đầu đếm thời gian tìm hình. Nếu trong giới hạn không thấy hình đạt ngưỡng thì bỏ qua trong lượt hiện tại và xét điều kiện tiếp theo.
2. Khi lần đầu thấy hình đạt ngưỡng trong thời gian tìm, đặt lại bộ đếm thời gian xét về 0. Nếu quan sát thấy hình đạt đủ **Ổn định ít nhất (ms)** trong thời gian xét thì dừng chờ, kiểm tra lại và chạy ngay nếu vẫn đạt, không đợi hết thời hạn.
3. Trong giai đoạn xét ổn định, một lần thấy ảnh không đạt sẽ đặt lại thời gian ổn định, nhưng **không** đặt lại thời hạn xét lần nữa. Hết thời hạn mà không thấy đủ ổn định thì bỏ qua trong lượt này.

Ví dụ đặt thời gian tìm / xét **500 ms**, ổn định ít nhất **250 ms**: tìm tối đa 500 ms; nếu khớp đúng lúc 400 ms thì bắt đầu tối đa 500 ms mới để xét ổn định; nếu đủ ổn định ở 250 ms sau đó sẽ chạy ngay. Một điều kiện có thể làm các điều kiện phía sau phải chờ gần **hai lần thời gian tìm / xét**. Điều kiện phía sau chờ điều kiện ưu tiên cao đang xét xong hoặc hết thời gian. Sau khi chạy xong toàn bộ chuỗi của một điều kiện, kể cả các thời gian chờ sau thao tác, app **xét tiếp điều kiện kế tiếp**, không quay lên đầu. Chỉ khi đã xét tới hết điều kiện cuối cùng (và chạy xong toàn bộ chuỗi nếu điều kiện đó đạt) mới quay lại từ đầu. Điều kiện xuất hiện sau khi vị trí xét đã đi qua chỉ được xét chạy ở lượt tiếp theo. Điều kiện không được phép chạy vì Một lần chưa mở lại, đang nghỉ hoặc đã đạt số lần tối đa được bỏ qua ngay. Điều kiện đã bỏ qua trong lượt đang xét không cản điều kiện phía sau trong lượt ấy. Không lưu công việc hoặc kết quả điều kiện cũ chờ chạy.

Thời gian 1–60.000 ms, mặc định 2.000 ms; không được nhỏ hơn thời gian ổn định ít nhất. Script cũ thiếu trường được nạp với 2.000 ms, hoặc ổn định ít nhất + 500 ms nếu lớn hơn 2.000; dùng **Lưu script** nếu muốn lưu. Để ví dụ 500 ms có hiệu lực, đặt ô này thành 500 cho từng điều kiện. Giá trị hợp lệ được ghi nhớ cho điều kiện tạo mới. Chọn thời gian xét có khoảng dư do lấy mẫu; nếu đặt sát thời gian ổn định, app có thể không lấy mẫu kịp để xác nhận.

Ảnh được lấy mẫu lần lượt, không đồng thời; thời gian chờ không chính xác đến từng mili giây. Ngoài bước xác nhận tùy chọn, không quét trong lúc thực hiện chuỗi và chờ sau; thời gian ổn định/tìm/xét đặt lại sau chuỗi, khi tạm dừng hoặc mất focus. Vị trí xét trong lượt được giữ khi F7 tạm dừng/tiếp tục hoặc mất focus. F8 dừng ngay, không chờ hết thời gian xét; khi F6 bắt đầu lượt chạy mới thì xét từ đầu. Mất focus trong chuỗi vẫn ngắt chuỗi để an toàn, nên không bảo đảm mọi thao tác của chuỗi đó đã hoàn tất.

- **Một lần** vẫn cần quan sát không đạt đủ ô **Không đạt ổn định để chạy lại** trước khi chạy tiếp. **Lặp** có nghỉ sau chuỗi; các chế độ này không bị thay bằng logic tìm hình mới.
- Mọi thao tác trong chuỗi, gồm lặp, giữ và chờ sau thao tác, được thực hiện xong trước khi xét điều kiện khác. Cùng số thứ tự chỉ là gửi gần đồng thời.

## Nhật ký chưa kích hoạt

Trước lần kích hoạt thành công đầu tiên không ghi dòng “Chưa kích hoạt”. Sau mỗi lần kích hoạt, app cho phép ghi các dòng này trong một lượt xét có thứ tự. Khi một điều kiện được phép chạy đã **hết thời gian tìm hình** hoặc **hết thời gian xét ổn định** mà không kích hoạt, ghi:

`22:01:49.025: Luồng 1 / Điều kiện 2: Chưa kích hoạt (Độ ổn định: 200/500, Độ giống: 0.9862/0.9000, Độ giống màu: 0.8500/0.8000, Độ sáng: 0.3615/0.3000)`

Tử số độ ổn định là thời gian khớp liên tục **được quan sát gần nhất trước hạn**; mẫu số là **thời gian tìm / xét tối đa**, đơn vị ms. Nếu không thấy hình khớp thì tử số là 0. Độ giống và độ sáng đo ở lần quan sát xác định quá hạn; mỗi số sau dấu `/` là ngưỡng của điều kiện. Do lấy mẫu không liên tục, không khẳng định ảnh luôn giữ trạng thái giữa hai lần đo.

App không ghi “Chưa kích hoạt” khi vẫn đang chờ. Trường hợp không thể bắt đầu xét vì chế độ Một lần chưa mở lại, đang nghỉ hoặc đạt số lần tối đa, app **bỏ qua ngay và ghi một dòng Bỏ qua** kèm lý do, điểm và ngưỡng; không chờ hết thời gian tìm hình vì nó không thể được chạy trong lúc đó. Trường độ ổn định ghi `chưa xét/thời gian xét` vì bộ đếm chưa bắt đầu. Nếu đủ ổn định nhưng kiểm tra lại không đạt trước khi gửi thao tác, app ghi “Bỏ qua (kiểm tra lại không đạt...)”. Các dòng Bỏ qua cũng chỉ ghi trong lượt sau khi có kích hoạt, mỗi điều kiện tối đa một lần trong lượt đó. Nếu qua cả lượt xét không có kích hoạt, app **ngừng ghi dòng chưa kích hoạt**, nhưng vẫn tiếp tục quét và xét bình thường; khi có một điều kiện kích hoạt thành công, việc ghi lại được mở cho lượt tiếp theo. Không ghi lại log của các lượt trước. Có thể bật **Hiện chẩn đoán chi tiết** để xem thêm lý do và hết thời gian xét.

## Nhật ký thao tác

Mỗi khi một điều kiện chính thức được kích hoạt, nhật ký mặc định ghi dòng:

`19:22:24.069: Luồng 3 / Kích hoạt Điều kiện 1 (Độ giống: 0.9351, Độ giống màu: 0.8500/0.8000, Độ sáng: 0.5460)`

Các giá trị là số thực tế trong lần kiểm tra lại ngay trước khi bắt đầu chuỗi, không phải ngưỡng. Độ sáng là trung bình của các pixel trong mặt nạ; ví dụ 0.5460 tương đương 54,60% thang 0–1. Dòng không xác nhận game nhận thao tác. Nếu kiểm tra lại không đạt, điều kiện không được chạy và không có dòng kích hoạt.

Nhật ký mặc định cũng ghi từng lần nhấn và nhả theo dạng:

`19:22:18.790: Luồng 3 / Điều kiện 2 / Thao tác Q · số thứ tự 6 · NHẤN · lần 1/1`

Tên thao tác giống nhãn trong cây: phím là tên phím, chuột là nút và vị trí; số thứ tự là nhóm trong điều kiện. Lặp nhiều lần sẽ có dòng nhấn/nhả cho mỗi lần. Thời gian được ghi tại luồng thực hiện, không phải lúc giao diện hiển thị. NHẤN và NHẢ thể hiện API đã được gọi thành công, không xác nhận game nhận hoặc xử lý; `mouse_event` không cung cấp kết quả xác nhận. Khi bị ngắt, NHẢ KHẨN cho biết app đã cố gọi API nhả thành công, không khẳng định ứng dụng đích đã xử lý.

Thông báo khởi động, dừng, lỗi và mất focus vẫn hiển thị. Muốn xem điểm nhận diện, lý do lựa chọn, chờ sau và các chi tiết cũ thì bật **Hiện chẩn đoán chi tiết** trước khi tái hiện; các dòng chi tiết bị ẩn trước khi bật sẽ không được khôi phục. Khi có mất focus, log có thể chứa tiêu đề cửa sổ khác: kiểm tra thông tin riêng tư trước khi chia sẻ. Log chỉ hiển thị trong app, không tự ghi ra file hay tải lên mạng.

Bản này thực hiện tìm hình rồi xét ổn định theo hai giai đoạn; chưa xác định nguyên nhân game có vẻ dùng Q khi điều kiện không chứa Q. Ảnh được chụp lần lượt, không đồng thời; sau mỗi chuỗi xét tiếp điều kiện sau, hết lượt mới quay lại đầu; không lưu điều kiện cũ. Ở chế độ Một lần, mặc định cần quan sát không đạt ổn định 500 ms trước khi được phép chạy lại; **Lặp** dùng thời gian nghỉ sau chuỗi. Xem phần bên dưới để biết giới hạn.

## Ghi nhớ thiết lập và lưu script

- Không còn thông báo chọn nơi lưu khi mở app. Những giá trị hợp lệ vừa chỉnh trong biểu mẫu điều kiện/thao tác được ghi nhớ để dùng khi tạo điều kiện/thao tác mới, kể cả sau khi đóng và mở lại.
- Mặc định app tự ghi **`MacroVision-defaults.json` cạnh `MacroVision.exe`**. Khi chạy mã nguồn bằng Python, file này nằm cạnh `app.py`. File này chỉ chứa các giá trị mặc định biểu mẫu, **không chứa script, ảnh mẫu hay mặt nạ**.
- Bấm **Vị trí lưu thiết lập…** để chọn thư mục khác. App lưu defaults vào thư mục đã chọn và ghi **`MacroVision-location.json` cạnh EXE** để nhớ vị trí đó cho lần sau. Nếu đổi thư mục, file defaults cũ không bị xóa; file đích đã tồn tại sẽ cần xác nhận trước khi thay. App không ghi đè file không đúng định dạng defaults. Cần quyền ghi tại thư mục EXE (để ghi file vị trí) và thư mục được chọn; lỗi được hiển thị, không tự chuyển sang thư mục ẩn khác.
- **Script là phần riêng:** dùng **Mở script** để mở và **Lưu script** để chủ động chọn file và lưu. Bản sửa này **không tự lưu script** sau khi chỉnh sửa; nhớ bấm Lưu script trước khi thoát. App hỏi nếu chuẩn bị bỏ các thay đổi script chưa lưu. File script cũ mở được; defaults nhúng trong file script cũ không tự thay defaults toàn ứng dụng.
- App không tự đọc, ghi hay xóa phiên cũ tại `%LOCALAPPDATA%\MacroVision\session.json`. Nếu cần, bạn có thể tự mở phiên cũ đó, rồi lưu script sang file khác.
- Khi ghi JSON an toàn, app tạo file tạm trong cùng thư mục rồi thay file đích. Thay đổi chưa hợp lệ không được ghi nhớ; sửa trường sai trước khi chuyển mục/chạy.

## Chạy và phím tắt

- Đã bỏ hoàn toàn **tùy chọn chạy thử** khỏi giao diện. Mọi lượt bắt đầu đều là **gửi thao tác thật**.
- **F6**: bắt đầu ngay. Đưa cửa sổ đích lên trước rồi nhấn F6; app dùng cửa sổ đang ở phía trước làm đích. Bấm nút Bắt đầu khi chính app đang ở phía trước sẽ bị từ chối để tránh gửi nhầm; hãy dùng F6 từ cửa sổ đích. **F7**: tạm dừng/tiếp tục; lần nhấn đang giữ được nhả trước khi nghỉ. **F8**: dừng, cố gắng nhả đầu vào ngay. Không dùng F6–F8 làm thao tác macro. Khi ô ghi nhận phím đang có focus, cả F6–F8 đều bị bỏ qua; hãy rời ô hoặc bấm nút Dừng.
- Trước khi chạy trong game, có thể thử script đơn giản trên cửa sổ an toàn như Notepad để quan sát các phím được gửi. Việc Windows chấp nhận lệnh không bảo đảm game xử lý lệnh đó. Macro có thể không phù hợp với quy định trò chơi; không có bảo đảm tránh bị ban.
- Nhận diện và marker trên màn hình chính; thay DPI, độ phân giải hoặc vị trí cửa sổ có thể làm lệch. Cả `SendInput` và `mouse_event` đều là đầu vào mô phỏng.

## Build EXE Windows

1. Giải nén, cài Python **3.12** và có kết nối Internet.
2. Chạy `build_exe.bat`; sau khi hoàn tất, chạy `dist\MacroVision.exe`. Đảm bảo thư mục chứa EXE cho phép ghi nếu muốn tự lưu thiết lập.
3. Có thể build bằng GitHub Actions với `.github/workflows/windows-build.yml`; tải artifact trong Actions.

Chưa build hoặc chạy thử thực tế trên Windows/game. EXE một file có thể giải nén thành phần chương trình vào thư mục tạm Windows khi chạy; đây không phải file script tự lưu.

## Kiểm thử

`python -m unittest discover -s tests -v`

Đã chạy 192 bài kiểm thử logic/giao diện trên Linux/Xvfb, gồm thứ tự quét, không có hàng đợi, chờ ổn định và hết hạn, không ngắt chuỗi, chế độ Một lần/Lặp, chống kích hoạt lại chập chờn, ghi log chẩn đoán, chờ sau thao tác, F7/F8 khi chờ, lưu defaults riêng và mở script cũ. Chưa kiểm thử Windows, DPI, input thật hoặc game.
